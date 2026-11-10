from datetime import date, timedelta
import pytest
from finops_agent.chat.models import PlanRequest
from finops_agent.consulting.ticket_lifecycle import task_presentation, matches_status
from finops_agent.consulting.followup import followups
from test_chat_operations import ops as operations_fixture


@pytest.mark.parametrize('status,kind,expected', [
    ('PROPOSED','finding','Por hacer'), ('APPROVED','finding','Por hacer'),
    ('REJECTED','finding','Por hacer'), ('MONITORING','finding','En seguimiento'),
    ('IMPLEMENTED','finding','En seguimiento'), ('IMPLEMENTED','onboarding','Resuelto'),
    ('RESOLVED','finding','Resuelto'), ('FALSE_POSITIVE','finding','Descartado'),
])
def test_historical_statuses_have_clear_user_meaning(status, kind, expected):
    assert task_presentation(dict(status=status,ticket_kind=kind))['visible_status']==expected


def plan(ops, status, **extra):
    ticket = ops.tickets(['FIN-001'])[0]
    request = PlanRequest(changes=[dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
        target_status=status,reason='Decisión explícita del usuario',**extra)])
    return ops.plan(request,'thread','turn-'+status)


def test_implementation_needs_no_intermediate_approval_state_but_cannot_close_without_data(container):
    ops = operations_fixture.__wrapped__(container)
    proposal = plan(ops,'IMPLEMENTED',append_note='Etiquetas aplicadas hoy')
    assert ops.tickets(['FIN-001'])[0]['status']=='PROPOSED'
    result = ops.apply(proposal['plan_id'],'thread','command',dict(actor='local-user',message_id='yes'))
    ticket = result['tickets'][0]
    assert ticket['status']=='IMPLEMENTED'
    assert ticket['followup']['event_date']==date.today().isoformat()
    assert task_presentation(ticket)['visible_status']=='En seguimiento'
    assert followups(ops.client)[0]['status']=='pending_data'
    with pytest.raises(ValueError,match='evidencia'):
        plan(ops,'RESOLVED')
    assert any(t.workflow_key=='verification:FIN-001' for t in ops.client.tickets.list())


def test_cancelling_an_action_preserves_task_and_reject_is_not_false_positive(container):
    ops = operations_fixture.__wrapped__(container)
    proposal = plan(ops,'IMPLEMENTED')
    ops.reject(proposal['plan_id'],'thread')
    ticket = ops.tickets(['FIN-001'])[0]
    assert ticket['status']=='PROPOSED' and task_presentation(ticket)['visible_state']=='todo'
    with pytest.raises(ValueError,match='puntual'):
        plan(ops,'FALSE_POSITIVE',append_note='Fue un evento puntual',evidence_refs=['message:turn'])
    genuine = plan(ops,'FALSE_POSITIVE',append_note='La factura estaba duplicada: hallazgo incorrecto',
                   evidence_refs=['message:correction'])
    assert genuine['status']=='pending'


def test_deferred_tasks_remain_recoverable_and_return_when_due(container):
    ops = operations_fixture.__wrapped__(container)
    with pytest.raises(ValueError,match='fecha futura'):
        plan(ops,'SNOOZED')
    due = (date.today()+timedelta(days=2)).isoformat()
    proposal = plan(ops,'SNOOZED',fields=dict(snoozed_until=due),evidence_refs=['message:user'])
    ticket = ops.apply(proposal['plan_id'],'thread','command',dict(actor='local-user',message_id='yes'))['tickets'][0]
    assert task_presentation(ticket)['deferred']
    assert not task_presentation({**ticket,'snoozed_until':date.today().isoformat()})['deferred']
    assert task_presentation({**ticket,'snoozed_until':None})['deferred']


@pytest.mark.parametrize('status,query,expected', [
    ('PROPOSED','Por hacer',True), ('APPROVED','Por hacer',True), ('REJECTED','Por hacer',True),
    ('IMPLEMENTED','En seguimiento',True), ('RESOLVED','En seguimiento',False),
    ('FALSE_POSITIVE','Descartado',True), ('APPROVED','PROPOSED',False),
])
def test_visible_filters_match_the_list_and_preserve_internal_api_filters(status, query, expected):
    assert matches_status(dict(status=status),query)==expected


def test_invalid_filter_is_explicit_instead_of_returning_an_empty_board():
    with pytest.raises(ValueError,match='filtrar tareas'):
        matches_status(dict(status='PROPOSED'),'invalid')
