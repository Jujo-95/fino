from unittest.mock import patch
import pytest
from finops_agent.chat.operations import TicketOperations
from finops_agent.chat.models import PlanRequest
from finops_agent.chat.authorization import explicit_order, authorized_directly
from finops_agent.models import Finding, ClientProfile, TicketUpdate


@pytest.fixture
def ops(container):
    client = container.client('acme')
    base = dict(capability='allocation', maturity_tier='Walk', allocation_mode='Showback', severity='HIGH',
        sub_account_id='all',service_name='all',period_bucket='2026-10',kpi_value=10,
        estimated_monthly_impact_usd=100,title='Tag gap',evidence_summary='A measured gap',
        recommended_action='Apply tags',capability_citation_url='https://www.finops.org/framework/capabilities/allocation/')
    for metric in ('unallocated_cost_pct','allocation_accuracy_index'):
        client.tickets.create(Finding(**base,kpi_name=metric))
    return TicketOperations(client)


def proposal(ops, status='APPROVED'):
    tickets = ops.tickets(['FIN-001','FIN-002'])
    return ops.plan(PlanRequest(changes=[dict(ticket_id=t['ticket_id'],expected_revision=t['revision'],
        target_status=status,append_note='Owner approved',reason='User decision') for t in tickets]),'thread','turn')


def test_batch_is_idempotent_and_keeps_notes_and_audit(ops):
    plan = proposal(ops)
    auth = dict(actor='local-user',message_id='user-message')
    result = ops.apply(plan['plan_id'],'thread','command',auth)
    assert all(t['status']=='APPROVED' for t in result['tickets'])
    assert ops.apply(plan['plan_id'],'thread','command',auth) == result
    assert ops.client.engine.conn.execute('SELECT count(*) FROM ticket_commands').fetchone()[0] == 1
    ticket = ops.tickets(['FIN-001'])[0]
    second = ops.plan(PlanRequest(changes=[dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
        append_note='Implementation validated',reason='Owner verification')]),'thread','turn-2')
    updated = ops.apply(second['plan_id'],'thread','command-2',auth)['tickets'][0]
    assert updated['resolution_note'] == 'Owner approved\n\nImplementation validated'
    assert len(updated['note_history']) == 2
    ops.client.tickets.recover()
    assert 'Implementation validated' in (ops.client.workspace/'tickets/FIN-001.md').read_text()


@pytest.mark.parametrize('failure',['stale','file','unauthorized'])
def test_batch_failure_never_leaves_partial_changes(ops, failure):
    plan = proposal(ops)
    before = [t.model_dump() for t in ops.client.tickets.list()]
    if failure == 'stale':
        ops.client.tickets.update('FIN-002',TicketUpdate(
            status='SNOOZED',resolution_note='Changed independently'))
        before = [t.model_dump() for t in ops.client.tickets.list()]
        with pytest.raises(ValueError,match='Cambió'):
            ops.apply(plan['plan_id'],'thread','command',dict(actor='local-user',message_id='ok'))
    elif failure == 'unauthorized':
        with pytest.raises(ValueError,match='autorización'):
            ops.apply(plan['plan_id'],'thread','command',{})
    else:
        from finops_agent.engine.ticket_manager import atomic_write_text
        calls = 0
        def fail_once(path,text):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('Explicit disk failure fixture')
            return atomic_write_text(path,text)
        with patch('finops_agent.engine.ticket_manager.atomic_write_text',side_effect=fail_once):
            with pytest.raises(OSError):
                ops.apply(plan['plan_id'],'thread','command',dict(actor='local-user',message_id='ok'))
    assert [t.model_dump() for t in ops.client.tickets.list()] == before
    assert ops.client.engine.conn.execute('SELECT count(*) FROM ticket_commands').fetchone()[0] == 0
    assert all((ops.client.workspace/'tickets'/f"{t['ticket_id']}.md").read_text().find(t['status'])>=0 for t in before)


def test_plan_and_receipts_are_scoped_to_thread_and_client(ops,container):
    plan = proposal(ops)
    with pytest.raises(KeyError):
        ops.read(plan['plan_id'],'other-thread')
    other = container.onboard(ClientProfile(client_id='other',client_name='Other'))
    with pytest.raises(KeyError):
        TicketOperations(other).read(plan['plan_id'],'thread')
    with pytest.raises(ValueError):
        TicketOperations(other).tickets(['FIN-001'])


@pytest.mark.parametrize('text,allowed',[
    ('mueve #FIN-001 y #FIN-002 a falsos positivos porque fue aprobado',True),
    ('Qué hago hoy con FIN-001 y FIN-002',False),
    ('no mueve FIN-001 a implementado porque sí',False),
    ('mueve todos a implementados porque sí',False),
    ('añade nota a #FIN-001: Validado por el dueño',True)])
def test_direct_authorization_has_concrete_scope(text,allowed):
    order = explicit_order(text)
    assert bool(order) is allowed
    if order:
        changes = [dict(ticket_id=key,target_status=order['target_status'],append_note=order['note']) for key in order['ticket_ids']]
        assert authorized_directly(dict(changes=changes),dict(direct_order=order))
        changes[0]['append_note'] = 'A different decision'
        assert not authorized_directly(dict(changes=changes),dict(direct_order=order))


def test_same_authorized_turn_cannot_append_the_same_note_again(ops):
    first = proposal(ops)
    ops.apply(first['plan_id'],'thread','command',dict(actor='local-user',message_id='user-message'))
    tickets = ops.tickets(['FIN-001','FIN-002'])
    repeated = ops.plan(PlanRequest(changes=[dict(ticket_id=t['ticket_id'],expected_revision=t['revision'],
        target_status='APPROVED',append_note=' Owner approved ',reason='Reworded by the model') for t in tickets]),'thread','turn')
    assert repeated['plan_id']==first['plan_id']
    assert len(ops.tickets(['FIN-001'])[0]['note_history'])==1
