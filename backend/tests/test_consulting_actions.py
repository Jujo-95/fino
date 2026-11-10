from datetime import date
from uuid import uuid4
import pytest
from finops_agent.chat.models import PlanRequest
from finops_agent.chat.operations import revision
from finops_agent.consulting.models import Implementation
from finops_agent.consulting.verification import register, verifications
from finops_agent.consulting.actions import validate_dependencies
from test_consulting import confirm
from test_chat_operations import ops


def test_dependency_cycle_rejects_entire_batch(container):
    operations = ops.__wrapped__(container)
    tickets = operations.tickets(['FIN-001', 'FIN-002'])
    changes = [dict(ticket_id=t['ticket_id'],expected_revision=t['revision'],reason='Plan',
        fields=dict(action_details=dict(dependencies=[tickets[1-i]['ticket_id']],steps=['Review scope']))) for i,t in enumerate(tickets)]
    plan = operations.plan(PlanRequest(changes=changes), 'test', 'turn')
    with pytest.raises(ValueError,match='ciclo'):
        operations.apply(plan['plan_id'], 'test', 'command', dict(actor='local-user',message_id='ok'))
    assert all(not t.action_details.dependencies for t in operations.client.tickets.list())
    assert operations.client.engine.conn.execute('SELECT count(*) FROM ticket_commands').fetchone()[0]==0


@pytest.mark.parametrize('dependency', ['FIN-001','FIN-999'])
def test_dependencies_must_exist_and_not_self_reference(container, dependency):
    operations = ops.__wrapped__(container)
    ticket = operations.client.tickets.list()[0]
    ticket.action_details.dependencies.append(dependency)
    with pytest.raises(ValueError):
        validate_dependencies(operations.client, [ticket])


def test_implementation_never_proves_savings_and_waits_for_data(container,csv_path):
    operations = ops.__wrapped__(container)
    client = operations.client
    client.engine.ingest_focus_csv('acme', csv_path)
    ticket = client.tickets.list()[0].model_copy(update={'status':'IMPLEMENTED',
        'sub_account_id':'prod-payments','service_name':'Amazon EC2'})
    client.tickets._commit(ticket)
    confirm(client, dict(data_latency_days=1))
    body = Implementation(command_id=uuid4().hex,expected_revision=revision(ticket),
        effective_date=date(2026,10,10),evidence='Horario aplicado, evidencia del cambio.')
    first = register(client,ticket.ticket_id,body)
    assert register(client,ticket.ticket_id,body)==first
    result = verifications(client)[0]
    assert result['status']=='no_improvement' and result['attributed_savings'] is None
    with client.engine.atomic_tx() as tx:
        tx.execute("DELETE FROM focus_usage WHERE CAST(ChargePeriodStart AS DATE)='2026-10-11'")
    assert verifications(client)[0]['status']=='pending_data'


def test_complete_post_data_with_incomplete_baseline_is_inconclusive(container,csv_path):
    operations = ops.__wrapped__(container)
    client = operations.client
    client.engine.ingest_focus_csv('acme', csv_path)
    ticket = client.tickets.list()[0].model_copy(update={'status':'IMPLEMENTED',
        'sub_account_id':'prod-payments','service_name':'Amazon EC2'})
    client.tickets._commit(ticket)
    confirm(client, dict(data_latency_days=0))
    register(client,ticket.ticket_id,Implementation(command_id=uuid4().hex,expected_revision=revision(ticket),
        effective_date=date(2026,10,3),evidence='Cambio validado externamente'))
    assert verifications(client)[0]['status']=='inconclusive'
