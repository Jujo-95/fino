from typing import Any
from ..consulting.ticket_lifecycle import task_presentation


def ticket_context(ticket: dict[str, Any], summary: bool = False) -> dict[str, Any]:
    ticket = {**ticket, **task_presentation(ticket)}
    if summary:
        keys = ('ticket_id','title','status','severity','capability','sub_account_id','service_name',
                'followup','tags','estimated_monthly_impact_usd','revision','updated_at_utc',
                'visible_state','visible_status','deferred','snoozed_until','next_step')
        return {key:ticket.get(key) for key in keys}
    return {**ticket, 'resolution_note':ticket['resolution_note'][-3000:],
        'note_history':[{**note,'text':note.get('text','')[-1500:]} for note in ticket.get('note_history', [])[-3:]],
        'notes_truncated':len(ticket['resolution_note'])>3000 or len(ticket.get('note_history', []))>3}


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {**plan,'before':[{key:ticket.get(key) for key in ('ticket_id','title','status','ticket_kind','revision','severity','recommended_action','estimated_monthly_impact_usd','evidence_summary','kpi_value','followup','tags')}
                            for ticket in plan['before']]}
