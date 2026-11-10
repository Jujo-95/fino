from uuid import uuid4
import pytest
import test_ticket_followup as helpers
from finops_agent.chat.models import PlanRequest
from finops_agent.chat.operations import revision
from finops_agent.chat.store import ChatStore
from finops_agent.chat.tools import ToolContext
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.agents_v2.sql import query
from finops_agent.consulting.followup import evaluate_followup
from finops_agent.consulting.followup_review import record_followup_review


@pytest.fixture
def review_ops(container,csv_path):
    ops = helpers.monitoring.__wrapped__(container,csv_path)
    t = ops.tickets(['FIN-001'])[0]
    followup = helpers.followup_plan().model_copy(update=dict(check='specialist_review'))
    plan = ops.plan(PlanRequest(changes=[dict(ticket_id=t['ticket_id'],expected_revision=t['revision'],
        target_status='MONITORING',fields=dict(followup=followup.model_dump(mode='json')),
        reason='Observar con revisión especializada')]),'test','turn')
    ops.apply(plan['plan_id'],'test','command',dict(actor='local-user',message_id='yes'))
    store = ChatStore(ops.client)
    thread = store.create(ORCHESTRATOR)
    thread['turn_id'] = uuid4().hex
    store.save(thread)
    return ops,ToolContext(container,'acme',thread['thread_id'],thread['turn_id'])


def test_specialist_review_requires_real_current_window_evidence_and_invalidates_on_change(review_ops):
    ops,ctx = review_ops
    ticket = ops.client.tickets.list()[0]
    assert evaluate_followup(ops.client,ticket)['status']=='needs_review'
    with pytest.raises(ValueError,match='consultas reales'):
        record_followup_review(ctx,ticket.ticket_id,revision(ticket),'criterion_met','Conclusión sin evidencia.',[])
    result = query(ops.client,"SELECT ServiceName, avg(EffectiveCost) AS avg_cost FROM focus_data_table WHERE SubAccountId='ml-platform' AND ServiceName='Vertex AI' GROUP BY 1",
                   '2026-10-11','2026-10-14',None)
    ctx.record('query_finance',result)
    record_followup_review(ctx,ticket.ticket_id,revision(ticket),'criterion_met',
        'El coste del servicio regresó al rango acordado; no acredita eficiencia operativa.',[result['evidence_id']])
    assert evaluate_followup(ops.client,ticket)['status']=='criterion_met'
    assert ops.client.tickets.list()[0].status=='MONITORING'
    ops.client.engine.conn.execute("UPDATE focus_usage SET EffectiveCost=200 WHERE ServiceName='Vertex AI' AND CAST(ChargePeriodStart AS DATE)='2026-10-12'")
    assert evaluate_followup(ops.client,ticket)['status']=='needs_review'


def test_another_client_has_no_access_to_followup_or_review(review_ops,container):
    from finops_agent.models import ClientProfile
    from finops_agent.chat.operations import TicketOperations
    from finops_agent.consulting.followup import followups
    container.onboard(ClientProfile(client_id='other',client_name='Other client'))
    client = container.client('other')
    assert followups(client)==[]
    with pytest.raises(ValueError,match='existir en este cliente'):
        TicketOperations(client).tickets(['FIN-001'])


def test_missing_latency_never_satisfies_closure_even_with_complete_billing(review_ops):
    from finops_agent.consulting.store import ConsultingStore
    ops,_ = review_ops
    store = ConsultingStore(ops.client)
    with ops.client.engine.atomic_tx() as tx:
        store.put(tx,'context','current',dict(values={}))
    assert evaluate_followup(ops.client,ops.client.tickets.list()[0])['status']=='pending_data'


@pytest.mark.parametrize('start,end,valid',[
    ('2026-10-11','2026-10-14',True),
    ('2026-10-11T00:00:00Z','2026-10-14T00:00:00Z',True),
    ('2026-10-14','2026-10-11',False),
    ('2026-10-11','2026-10-11',False),
    ('2025-01-01','2026-10-11',False),
    ('2026-10-11T00:00:00-05:00','2026-10-14T00:00:00-05:00',False)])
def test_followup_query_windows_are_bounded_utc_intervals(start,end,valid):
    from finops_agent.agents_v2.sql import validate_query_window
    if valid:
        validate_query_window(start,end)
    else:
        with pytest.raises(ValueError):
            validate_query_window(start,end)
