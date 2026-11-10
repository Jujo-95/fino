"""Reevaluation records observations; transitions still require explicit approval."""
from typing import Any
from .ticket_triage import mark_attention


def reevaluate(client: Any, result: dict[str,Any], run_id: str) -> None:
    observed = {(f['capability'],f['sub_account_id'],f['service_name'],f['kpi_name']) for f in result['findings']}
    measured = {m['capability'] for m in result['measurements'] if m['value'] is not None}
    for ticket in client.tickets.list():
        identity = (ticket.capability,ticket.sub_account_id,ticket.service_name,ticket.kpi_name)
        if ticket.ticket_kind!='finding' or ticket.status not in ('PROPOSED','APPROVED') or identity in observed:
            continue
        if ticket.capability not in measured:
            continue
        reason = 'El hallazgo no se reproduce con los controles de esta lectura. Verifica la cobertura y el criterio antes de proponer cierre.'
        mark_attention(client,ticket,run_id,reason)
        result.setdefault('reevaluations',[]).append(dict(ticket_id=ticket.ticket_id,status='needs_review',
            summary=reason,suggested_status=None,evidence_refs=[q.get('query_id') for q in result['evidence']]))


def refresh_observation(client: Any, ticket: Any, observation: dict[str,Any], run_id: str) -> None:
    needs = observation['status'] in ('persists','criterion_met','needs_review')
    with client.engine.lock:
        client.tickets._commit(ticket.model_copy(update=dict(needs_attention=needs,
            attention_reason=observation['summary'] if needs else '',last_evaluated_run_id=run_id)))
