"""User-facing task states; historical workflow values stay persisted."""
from datetime import date
from typing import Any


def task_state(ticket: dict[str, Any]) -> str:
    status = ticket.get('status')
    if status == 'RESOLVED':
        return 'resolved'
    if status == 'FALSE_POSITIVE':
        return 'dismissed'
    if status == 'MONITORING':
        return 'monitoring'
    if status == 'IMPLEMENTED':
        return 'resolved' if ticket.get('ticket_kind') not in (None, 'finding') else 'monitoring'
    return 'todo'


def task_presentation(ticket: dict[str, Any]) -> dict[str, Any]:
    state = task_state(ticket)
    due = ticket.get('snoozed_until')
    deferred = ticket.get('status') == 'SNOOZED' and (not due or str(due) > date.today().isoformat())
    labels = dict(todo='Por hacer', monitoring='En seguimiento', resolved='Resuelto', dismissed='Descartado')
    return dict(visible_state=state, visible_status=labels[state], deferred=bool(deferred),
                next_step=ticket.get('recommended_action', ''))


def validate_defer(ticket: Any, change: Any) -> None:
    if change.target_status != 'SNOOZED':
        return
    until = change.fields.snoozed_until if change.fields else None
    if ticket.status == 'SNOOZED' and until is None:
        return
    if not until or until <= date.today():
        raise ValueError('Para recordar esta tarea más adelante indica fields.snoozed_until con una fecha futura.')


def matches_status(ticket: dict[str, Any], status: str | None) -> bool:
    if not status:
        return True
    aliases = {'por hacer':'todo','todo':'todo','en seguimiento':'monitoring','monitoring':'monitoring',
               'resuelto':'resolved','resolved':'resolved','descartado':'dismissed','dismissed':'dismissed'}
    if status == status.upper():
        if status not in ('PROPOSED','APPROVED','MONITORING','IMPLEMENTED','RESOLVED','FALSE_POSITIVE','REJECTED','SNOOZED'):
            raise ValueError('Usa Por hacer, En seguimiento, Resuelto o Descartado para filtrar tareas.')
        return ticket.get('status') == status
    if status.lower() not in aliases:
        raise ValueError('Usa Por hacer, En seguimiento, Resuelto o Descartado para filtrar tareas.')
    view = task_presentation(ticket)
    return bool(view['visible_state'] == aliases[status.lower()] and not view['deferred'])
