"""Validate and prepare mixed create/update batches without side effects."""
import json
from typing import Any
from ..models import FinOpsTicket, TicketContributor
from .models import PlanRequest


def before_changes(ops: Any, request: PlanRequest) -> list[dict[str,Any]]:
    before = []
    for change in request.changes:
        if change.action=='create':
            assert change.finding is not None
            values = change.finding.model_dump()
            json.dumps(values,allow_nan=False)
            if any(isinstance(v,str) and not v.strip() for v in values.values()):
                raise ValueError('Completa todos los campos del hallazgo con evidencia.')
            if change.finding.capability not in ('data-ingestion','allocation','anomaly-management','forecasting','budgeting','rate-optimization','usage-optimization'):
                raise ValueError('Usa una capacidad FinOps soportada para el hallazgo.')
            if ops.client.tickets.find_existing(change.finding):
                raise ValueError('Ya existe un ticket para este hallazgo. Consúltalo y propón actualizarlo.')
            before.append(dict(ticket_id=None,title=change.finding.title,status=None,revision=None))
        else:
            ticket = ops.tickets([change.ticket_id])[0]
            if change.expected_revision!=ticket['revision']:
                raise ValueError(f'{change.ticket_id} cambió; vuelve a consultarlo antes de proponer el lote.')
            from ..consulting.followup import validate_followup_transition
            validate_followup_transition(ops.client, FinOpsTicket.model_validate(ticket), change)
            before.append(ticket)
    return before


def prepare_batch(ops: Any, plan: dict[str,Any], authorization: dict[str,str]) -> tuple[list[Any],list[dict[str,Any]]]:
    from .operations import updated_ticket
    request = PlanRequest(changes=plan['changes'])
    current = before_changes(ops,request)
    tickets,created = [],0
    contributors = [TicketContributor(**item) for item in plan.get('contributors',[])]
    for change,document in zip(request.changes,current):
        if change.action=='create':
            ticket = ops.client.tickets.prepare_create(change.finding,contributors,created)
            created += 1
        else:
            ticket = updated_ticket(document,change,plan['thread_id'],authorization)
            merged = [*ticket.contributors,*[c for c in contributors if c not in ticket.contributors]]
            ticket = ticket.model_copy(update=dict(contributors=merged))
        tickets.append(FinOpsTicket.model_validate(ticket.model_dump()))
    from ..consulting.actions import validate_dependencies
    validate_dependencies(ops.client, tickets)
    return tickets,current
