"""One agenda, one next action, observable results; no model-derived percentages."""
from typing import Any
from .progress_objectives import objectives
from .progress_history import history_summary
from .ticket_lifecycle import task_presentation
from .progress_risk import urgent_budget


def attention(ticket: dict[str, Any]) -> dict[str, Any]:
    view = task_presentation(ticket)
    if view['visible_state'] in ('resolved','dismissed') or view['deferred']:
        return dict(kind='none',label='',reason='')
    if view['visible_state']=='monitoring':
        if ticket.get('last_evaluated_run_id') and ticket.get('needs_attention') and ticket.get('attention_reason'):
            return dict(kind='decision',label='Revisar resultado',reason=ticket['attention_reason'])
        return dict(kind='waiting',label='En seguimiento',reason='Esperamos comprobar el resultado con datos posteriores.')
    return dict(kind='new' if ticket.get('is_new') else 'none',label='Nueva' if ticket.get('is_new') else '',reason='')


def progress(client: Any, actions: list[dict[str, Any]], monitoring: list[dict[str, Any]]) -> dict[str, Any]:
    tickets = [t.model_dump(mode='json') for t in client.tickets.list()]
    goals = objectives(client,tickets)
    goal = next((g for g in goals if g['total'] and not g['complete']),next((g for g in reversed(goals) if g['total']),None))
    ids = set(goal['ticket_ids'])-set(goal['excluded']) if goal else set()
    available = [a for a in actions if a['ready'] and a.get('visible_state')=='todo']
    risk = urgent_budget(client)
    urgent = {t['ticket_id'] for t in tickets if risk and t['capability']=='budgeting' and t.get('last_evaluated_run_id')==risk['run_id']}
    available.sort(key=lambda a:(a['ticket_id'] not in urgent,a['ticket_id'] not in ids, -sum(a['ticket_id'] in b['blocked_by'] for b in actions),
        a.get('severity') not in ('CRITICAL','HIGH'),-(a.get('estimated_monthly_impact_usd') or 0),a['ticket_id']))
    candidate = available[0] if available else next((a for a in actions if a['ready'] and a.get('followup',{}).get('status') in ('criterion_met','needs_review','persists')),None)
    next_action = dict(candidate,reason=('Este paso continúa tu objetivo y puede desbloquear otras tareas.'
        if candidate['ticket_id'] in ids else candidate['reason'])) if candidate else None
    if next_action and next_action['ticket_id'] in urgent and risk:
        next_action.update(reason=risk['reason'],attention='urgent',urgency_evidence=risk)
    waiting = ('Por hoy no hay acciones disponibles. Esperamos datos o información para continuar.' if not next_action else None)
    return dict(objective=goal,objectives=goals,next_action=next_action,waiting_for=waiting,
        review_after=None,history=history_summary(client,tickets))


def agent_progress(value: dict[str, Any]) -> dict[str, Any]:
    goal = value['objective']
    return dict(objective={k:goal[k] for k in ('id','title','version','completed','total','percent','complete')} if goal else None,
        next_action=value['next_action'],waiting_for=value['waiting_for'],review_after=value['review_after'],
        history={k:value['history'][k] for k in ('resolved_total','resolved_this_week','observing','timezone','week_start')})
