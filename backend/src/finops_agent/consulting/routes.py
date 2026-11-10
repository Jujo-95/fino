from typing import Any
from fastapi import APIRouter, HTTPException
from ..api.routes import Container
from .models import ContextProposal, Decision, Implementation, ConsultingResponse
from .store import ConsultingStore
from .diagnosis import diagnosis
from .agenda import agenda
from .verification import register, verifications
from .supporting import SupportingInput, import_supporting, supporting_data
from .action_connectors import CloudActionRequest, simulate, approve

router = APIRouter(prefix='/api/v1/clients/{client_id}/consulting')


@router.post('/progress/next')
def start_next_progress(client_id: str, c: Container) -> dict[str, Any]:
    from .progress_objectives import next_cycle
    try:
        return next_cycle(c.client(client_id))
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/progress/{identity}/exclude')
def adjust_progress(client_id: str, identity: str, body: dict[str, Any], c: Container) -> dict[str, Any]:
    from .progress_objectives import exclude_step
    try:
        return exclude_step(c.client(client_id),identity,str(body['ticket_id']),int(body['version']))
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409,str(exc)) from exc


@router.post('/cloud-actions/simulate')
def simulate_action(client_id: str, body: CloudActionRequest, c: Container) -> dict[str, Any]:
    return simulate(c.client(client_id), body)


@router.post('/cloud-actions/{action_id}/approval')
def approve_action(client_id: str, action_id: str, body: Decision, c: Container) -> dict[str, Any]:
    return approve(c.client(client_id), action_id, body.decision == 'confirm', 'local-user')


@router.get('', response_model=ConsultingResponse)
def read(client_id: str, c: Container) -> dict[str, Any]:
    client = c.client(client_id)
    return dict(diagnosis=diagnosis(client), agenda=agenda(client), verifications=verifications(client))


@router.post('/context/proposals')
def propose(client_id: str, body: ContextProposal, c: Container) -> dict[str, Any]:
    try:
        return ConsultingStore(c.client(client_id)).propose(body, 'dashboard')
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/context/proposals/{proposal_id}')
def proposal(client_id: str, proposal_id: str, c: Container) -> dict[str, Any]:
    result = ConsultingStore(c.client(client_id)).get('context_proposal', proposal_id)
    if not result:
        raise KeyError('Propuesta no encontrada en este cliente.')
    return result


@router.post('/context/proposals/{proposal_id}/decision')
def decide(client_id: str, proposal_id: str, body: Decision, c: Container) -> dict[str, Any]:
    try:
        from .receipts import confirmation_receipt
        client = c.client(client_id)
        result = ConsultingStore(client).decide(proposal_id,body.decision,body.command_id)
        return confirmation_receipt(client,result,body.command_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/tickets/{ticket_id}/implementation')
def implementation(client_id: str, ticket_id: str, body: Implementation, c: Container) -> dict[str, Any]:
    try:
        client = c.client(client_id)
        result = register(client, ticket_id, body)
        from .workflow import sync_tasks
        sync_tasks(client)
        return result
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/verifications')
def outcomes(client_id: str, c: Container) -> list[dict[str, Any]]:
    return verifications(c.client(client_id))


@router.post('/supporting-data')
def import_data(client_id: str, body: SupportingInput, c: Container) -> dict[str, Any]:
    return import_supporting(c.client(client_id), body)


@router.get('/supporting-data')
def read_data(client_id: str, c: Container) -> dict[str, Any]:
    return supporting_data(c.client(client_id))
