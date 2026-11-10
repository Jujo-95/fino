"""A confirmation returns a persisted receipt, not an assistant assertion."""
from typing import Any
from .store import ConsultingStore
from .workflow import sync_tasks


def confirmation_receipt(client: Any, result: dict[str,Any], command_id: str) -> dict[str,Any]:
    if result.get('status')!='confirmed':
        return result
    store = ConsultingStore(client)
    cached = store.get('context_receipt',command_id)
    if cached:
        return dict(result,receipt=cached)
    sync_tasks(client)
    current = store.context()
    proposal = store.get('context_proposal',result['proposal_id'])
    keys = set(proposal['values']) if proposal else set()
    receipt = dict(persisted=True,client_id=client.profile.client_id,proposal_id=result['proposal_id'],
        confirmed_at=current.get('confirmed_at'),context_revision=current['revision'],
        values={key:current['values'].get(key) for key in keys},
        tickets=[dict(ticket_id=t.ticket_id,status=t.status) for t in client.tickets.list()
                 if t.workflow_key and t.workflow_key.startswith('requirement:') and t.workflow_key[12:] in keys])
    with client.engine.atomic_tx() as tx:
        store.put(tx,'context_receipt',command_id,receipt)
    return dict(result,receipt=receipt)
