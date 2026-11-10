"""Safe cloud action boundary: proposal, approval and idempotent receipt.

Provider adapters can be added behind this boundary. The default adapter never
mutates a cloud account; it records a simulation until a real adapter is wired.
"""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from ..engine.incremental_inputs import digest
from ..agents.audit_trace import timestamp
from .store import ConsultingStore


class CloudActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['aws', 'gcp', 'azure']
    operation: str = Field(min_length=2, max_length=120)
    target: str = Field(min_length=1, max_length=300)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)


def action_id(client: Any, request: CloudActionRequest) -> str:
    return request.idempotency_key or digest([client.profile.client_id, request.model_dump(mode='json')])


def simulate(client: Any, request: CloudActionRequest) -> dict[str, Any]:
    key = action_id(client, request)
    store = ConsultingStore(client)
    existing = store.get('cloud_action', key)
    if existing:
        return existing
    result = dict(action_id=key, client_id=client.profile.client_id, status='simulation',
        approval_required=True, provider=request.provider, operation=request.operation,
        target=request.target, parameters=request.parameters, created_at=timestamp(),
        adapter='simulation', message='No se modificó ningún recurso cloud; requiere aprobación explícita.')
    with client.engine.atomic_tx() as tx:
        store.put(tx, 'cloud_action', key, result)
    return result


def approve(client: Any, key: str, approved: bool, actor: str) -> dict[str, Any]:
    if actor != 'local-user':
        raise ValueError('Solo el usuario local puede aprobar una acción cloud.')
    store = ConsultingStore(client)
    action = store.get('cloud_action', key)
    if not action:
        raise KeyError('Acción cloud no encontrada en este cliente.')
    if action['status'] == 'executed' or action['status'] == 'rejected':
        return action
    action.update(status='approved' if approved else 'rejected', approved_by=actor, approved_at=timestamp())
    if approved:
        action.update(execution='simulation', message='Aprobada, pero el adaptador cloud real aún no está conectado.')
    with client.engine.atomic_tx() as tx:
        store.put(tx, 'cloud_action', key, action)
    return action
