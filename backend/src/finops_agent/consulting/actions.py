from typing import Any
from .models import ActionDetails
from .ticket_lifecycle import task_presentation


def validate_dependencies(client: Any, prepared: list[Any]) -> None:
    tickets = {t.ticket_id: t for t in client.tickets.list()}
    tickets.update({t.ticket_id: t for t in prepared})
    for ticket in tickets.values():
        for key in ticket.action_details.dependencies:
            if key not in tickets or key == ticket.ticket_id:
                raise ValueError('Las dependencias deben existir en este cliente y no apuntar al propio ticket.')
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError('Las dependencias del lote forman un ciclo.')
        if key in visited:
            return
        visiting.add(key)
        for other in tickets[key].action_details.dependencies:
            visit(other)
        visiting.remove(key)
        visited.add(key)
    for key in tickets:
        visit(key)
    for ticket in prepared:
        blocked = [k for k in ticket.action_details.dependencies if tickets[k].status not in ('IMPLEMENTED','RESOLVED')]
        if ticket.status in ('IMPLEMENTED','RESOLVED') and blocked:
            raise ValueError('Completa las dependencias antes de declarar la implementación.')


def action_summary(ticket: dict[str, Any], tickets: dict[str, Any]) -> dict[str, Any]:
    details = ActionDetails.model_validate(ticket.get('action_details', {}))
    blocked = [key for key in details.dependencies if key not in tickets or tickets[key]['status'] not in ('IMPLEMENTED','RESOLVED')]
    return dict(ticket_kind=ticket.get('ticket_kind', 'finding'), ticket_id=ticket['ticket_id'], title=ticket['title'], status=ticket['status'],
        **task_presentation(ticket),
        severity=ticket['severity'], capability=ticket['capability'], **details.model_dump(),
        blocked_by=blocked, ready=not blocked, estimated_monthly_impact_usd=ticket['estimated_monthly_impact_usd'],
        reason='Completar información necesaria' if ticket.get('ticket_kind')=='onboarding' else
        'Investigar los indicadores' if ticket.get('ticket_kind')=='analysis' else
        'Resolver una anomalía activa' if ticket['capability']=='anomaly-management' else 'Acción respaldada por el hallazgo',
        evidence_summary=ticket['evidence_summary'])
