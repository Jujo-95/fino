from datetime import date
from uuid import uuid4
import json
import pytest
from finops_agent.models import Finding
from finops_agent.chat.operations import TicketOperations
from finops_agent.chat.models import PlanRequest, ChatMessage, ResumeRequest
from finops_agent.chat.store import ChatStore
from finops_agent.consulting.followup_models import FollowupPlan
from finops_agent.consulting.followup import evaluate_followup
from finops_agent.consulting.report import report_followup
from finops_agent.agents_v2.registry import ORCHESTRATOR
from test_consulting import confirm
from test_chat_graph import wait_job


@pytest.fixture
def monitoring(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    client.engine.conn.execute("UPDATE focus_usage SET EffectiveCost=100 WHERE ServiceName='Vertex AI'")
    client.engine.conn.execute("UPDATE focus_usage SET EffectiveCost=10000 WHERE ServiceName='Vertex AI' AND CAST(ChargePeriodStart AS DATE)='2026-10-10'")
    confirm(client,dict(data_latency_days=0))
    client.tickets.create(Finding(capability='anomaly-management',maturity_tier='Walk',allocation_mode='N/A',
        severity='HIGH',sub_account_id='ml-platform',service_name='Vertex AI',period_bucket='2026-10',
        kpi_name='spike',kpi_value=9900,estimated_monthly_impact_usd=None,title='Pico puntual',
        evidence_summary='Test scoped deployment',recommended_action='Consultar al equipo',
        capability_citation_url='https://www.finops.org/framework/capabilities/anomaly-management/'))
    return TicketOperations(client)


def followup_plan():
    return FollowupPlan(reason='El equipo confirma un despliegue puntual.',event_date=date(2026,10,10),
        check='return_to_baseline',closure_criterion='Cada día posterior dentro del rango previo más 20%.')


def start_monitoring(ops):
    ticket = ops.tickets(['FIN-001'])[0]
    plan = ops.plan(PlanRequest(changes=[dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
        target_status='MONITORING',fields=dict(followup=followup_plan().model_dump(mode='json'),tags=['evento puntual']),
        append_note='Despliegue explicado; pendiente de confirmar normalización.',reason='Observar el evento')]),'test','start')
    auth = dict(actor='local-user',message_id='approval')
    receipt = ops.apply(plan['plan_id'],'test','command',auth)
    assert ops.apply(plan['plan_id'],'test','command',auth)==receipt
    return ops.client.tickets.list()[0]


@pytest.mark.parametrize('mutation,expected', [
    ('none','criterion_met'), ('missing','pending_data'), ('spike','persists'), ('baseline','needs_review')])
def test_window_excludes_event_and_requires_every_complete_day(monitoring,mutation,expected):
    ops = monitoring
    ticket = start_monitoring(ops)
    if mutation in ('missing','baseline'):
        day = '2026-10-12' if mutation=='missing' else '2026-10-05'
        ops.client.engine.conn.execute("DELETE FROM focus_usage WHERE ServiceName='Vertex AI' AND CAST(ChargePeriodStart AS DATE)=?",[day])
    if mutation=='spike':
        ops.client.engine.conn.execute("UPDATE focus_usage SET EffectiveCost=150 WHERE ServiceName='Vertex AI' AND CAST(ChargePeriodStart AS DATE)='2026-10-12'")
    result = evaluate_followup(ops.client,ticket)
    assert result['status']==expected
    assert ops.client.tickets.list()[0].status=='MONITORING'
    assert result['window_start']=='2026-10-11' and result['window_end_exclusive']=='2026-10-14'
    _,markdown = report_followup(ops.client)
    assert 'Seguimiento FIN-001' in markdown and 'requiere aprobación' in markdown


def test_closure_rechecks_data_at_approval_and_preserves_ticket(monitoring):
    ops = monitoring
    start_monitoring(ops)
    t = ops.tickets(['FIN-001'])[0]
    request = PlanRequest(changes=[dict(ticket_id=t['ticket_id'],expected_revision=t['revision'],
        target_status='RESOLVED',append_note='Normalización comprobada.',reason='Ventana completa')])
    plan = ops.plan(request,'close','turn')
    ops.client.engine.conn.execute("UPDATE focus_usage SET EffectiveCost=200 WHERE ServiceName='Vertex AI' AND CAST(ChargePeriodStart AS DATE)='2026-10-12'")
    with pytest.raises(ValueError,match='criterio'):
        ops.apply(plan['plan_id'],'close','close-command',dict(actor='local-user',message_id='yes'))
    assert ops.tickets(['FIN-001'])[0]['status']=='MONITORING'
    ops.client.engine.conn.execute("UPDATE focus_usage SET EffectiveCost=100 WHERE ServiceName='Vertex AI' AND CAST(ChargePeriodStart AS DATE)='2026-10-12'")
    ops.apply(plan['plan_id'],'close','close-command',dict(actor='local-user',message_id='yes'))
    assert ops.tickets(['FIN-001'])[0]['status']=='RESOLVED'


def test_monitoring_requires_plan_and_explained_event_is_not_false_positive(monitoring):
    ops = monitoring
    legacy = ops.client.tickets.list()[0].model_copy(update={'followup':None})
    ops.client.tickets._commit(legacy)  # Historical tickets can predate mandatory verification plans.
    ticket = ops.tickets(['FIN-001'])[0]
    with pytest.raises(ValueError,match='ventana'):
        ops.plan(PlanRequest(changes=[dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
            target_status='MONITORING',reason='Observar')]),'test','turn')
    start_monitoring(ops)
    ticket = ops.tickets(['FIN-001'])[0]
    with pytest.raises(ValueError,match='puntual'):
        ops.plan(PlanRequest(changes=[dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
            target_status='FALSE_POSITIVE',reason='Fue planeado')]),'test','other')


class FollowupDouble:
    async def complete(self,messages,tools):
        context = json.loads(messages[0]['content'].split('BACKEND CONTEXT:\n')[1])
        if context['application_results']:
            return dict(message=dict(role='assistant',content='Seguimiento guardado tras tu aprobación.'))
        last = messages[-1]
        if last['role']=='user':
            name,args = 'get_tickets',dict(ticket_ids=['FIN-001'])
        else:
            ticket = json.loads(last['content'])['tickets'][0]
            name,args = 'propose_ticket_followup',dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
                followup=followup_plan().model_dump(mode='json'),tags=['despliegue puntual'])
        return dict(message=dict(role='assistant',content='',tool_calls=[dict(id=uuid4().hex,type='function',
            function=dict(name=name,arguments=json.dumps(args)))]))


@pytest.mark.asyncio
async def test_agent_proposal_waits_for_user_then_atomically_applies(monitoring,container):
    original = monitoring.client.tickets.list()[0].followup
    container.llm = FollowupDouble()
    store = ChatStore(monitoring.client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Fue un despliegue puntual, ¿qué sugieres?',message_id=uuid4().hex))
    waiting = await wait_job(container,thread)
    assert waiting['status']=='waiting',waiting.get('error')
    assert monitoring.client.tickets.list()[0].followup == original
    assert monitoring.client.tickets.list()[0].status == 'PROPOSED'
    change = waiting['pending'][0]['changes'][0]
    assert change['target_status']=='MONITORING' and change['fields']['followup']['observation_days']==3
    container.chat.start('acme',thread['thread_id'],ResumeRequest(decision='approve',
        plan_ids=[waiting['pending'][0]['plan_id']],message_id=uuid4().hex))
    ready = await wait_job(container,thread)
    assert ready['status']=='ready',ready.get('error')
    ticket = monitoring.client.tickets.list()[0]
    assert ticket.status=='MONITORING' and ticket.tags==['despliegue puntual']
    assert ticket.followup and ticket.followup.reason==followup_plan().reason
    assert 'Seguimiento desde' in ticket.resolution_note
