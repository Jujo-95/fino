from typing import Any
from ..engine.incremental_inputs import digest
from .workflow import sync_tasks
from .actions import action_summary
from .ticket_lifecycle import task_presentation


def agenda(client: Any) -> dict[str, Any]:
    report = sync_tasks(client)
    tickets = {t.ticket_id: t.model_dump(mode='json') for t in client.tickets.list()}
    items = [action_summary(t, tickets) for t in tickets.values()
             if task_presentation(t)['visible_state'] in ('todo','monitoring') and not task_presentation(t)['deferred']]
    from .followup import followups
    monitoring = followups(client)
    observations = {o['ticket_id']:o for o in monitoring}
    for action in items:
        if action['ticket_id'] in observations:
            observation = observations[action['ticket_id']]
            action.update(followup=observation,ready=action['ready'] and observation['status']!='pending_data',reason=observation['summary'])
    items.sort(key=lambda a: (not a['ready'], bool(a['blocked_by']), a['severity'] not in ('CRITICAL', 'HIGH'),
        a['ticket_kind'] != 'onboarding', a['capability'] != 'anomaly-management', {'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3}[a['severity']],
        a['estimated_monthly_impact_usd'] is None, -(a['estimated_monthly_impact_usd'] or 0), a['ticket_id']))
    requirements = report['requirements']
    actionable = [r for r in requirements if r['id'] not in ('invoice', 'contracts', 'utilization')]
    from .progress import progress
    advancement = progress(client,items,monitoring)
    chosen = advancement['next_action']
    items.sort(key=lambda a: a['ticket_id']!=(chosen or {}).get('ticket_id'))
    return dict(progress=advancement,client_id=client.profile.client_id, revision=digest([report['revision'],items,advancement]),
        evaluated_at=report['evaluated_at'], data_through=report['data_through'],
        evidence_refs=report['evidence_refs'], actions=items, top_actions=[a for a in items if a['ready']][:3],
        monitoring=monitoring, requirements=requirements, next_requirement=actionable[0] if actionable else None,
        context_revision=report['context']['revision'])
