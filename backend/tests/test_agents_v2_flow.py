import json
from uuid import uuid4
import pytest
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.chat.models import ChatMessage
from finops_agent.chat.store import ChatStore
from finops_agent.chat.tools import ToolContext
from finops_agent.agents_v2.reports import save_report_document
from finops_agent.agents_v2.delegation import delegate
from finops_agent.engine.run_audit import RunAuditStore
from test_chat_graph import wait_job


def call(name,args):
    return dict(message=dict(role='assistant',content='',tool_calls=[dict(id=uuid4().hex,type='function',
        function=dict(name=name,arguments=json.dumps(args)))]))


class FleetDouble:
    calls = 0
    async def complete(self,messages,tools):
        self.calls += 1
        assert 'App runtime contract' in messages[0]['content']
        names = {item['function']['name'] for item in tools}
        last = messages[-1]
        if last['role']=='user':
            if 'save_report' in names:
                return call('consult_specialist',dict(specialist='v2-budget-anomaly-operator',question='Valida costos del periodo.'))
            return call('query_finance',dict(sql='SELECT sum(EffectiveCost) AS cost FROM focus_data_table'))
        if 'save_report' not in names:
            result = json.loads(last['content'])
            assert result['client_id']=='acme' and result['rows'][0]['cost']==49110
            return dict(message=dict(role='assistant',content=json.dumps(dict(agent='Budget & Anomaly Operator',metrics=[dict(name='actual_cost',value=49110)],findings=[],dataGaps=[]))))
        data = json.loads(last['content'])
        if data.get('status')=='saved':
            return dict(message=dict(role='assistant',content='Informe guardado en Reportes.'))
        assert data['specialist']=='v2-budget-anomaly-operator' and '49110' in data['summary']
        return call('save_report',dict(markdown='# Informe\nGasto observado: 49 110 USD.',structured_report=dict(client_id='acme',report=dict(clientId='acme',period='2026-10',currency='USD'),summary=dict(totalSpend=49110),findings=[],tickets=dict(proposedActions=[]),dataGaps=[])))


@pytest.mark.asyncio
async def test_v2_delegates_uses_real_duckdb_and_saves_dual_report(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    container.llm = FleetDouble()
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Genera el informe.',message_id=uuid4().hex))
    ready = await wait_job(container,thread)
    assert ready['status']=='ready',ready.get('error')
    assert ready['changed'] and ready['messages'][-1]['content']=='Informe guardado en Reportes.'
    records = RunAuditStore(client.workspace).list()
    assert len(records)==1
    record = RunAuditStore(client.workspace).detail(records[0]['run_id'])
    assert record['agent_generation']=='2.0' and record['structured_report']['client_id']=='acme'
    assert (client.workspace/'reports'/(record['run_id']+'.json')).exists()
    assert not any(t.ticket_kind=='finding' for t in client.tickets.list()) and len(store.list())==1
    assert container.llm.calls==5
    ctx = ToolContext(container,'acme',thread['thread_id'],ready['turn_id'])
    assert (await delegate(ctx,'v2-budget-anomaly-operator','Valida costos del periodo.'))['specialist']=='v2-budget-anomaly-operator'
    assert container.llm.calls==5
    previous = ctx.evidence.report(None)
    assert previous['run_id']==record['run_id'] and previous['structured_report']['client_id']=='acme'


def test_report_submission_idempotent_and_scope_checked(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    thread.update(turn_id='test',ticket_refs=[])
    store.save(thread)
    ctx = ToolContext(container,'acme',thread['thread_id'],'test')
    first = save_report_document(ctx,'# Reporte',dict(client_id='acme',findings=[]))
    assert save_report_document(ctx,'# Reporte',dict(client_id='acme',findings=[]))==first
    assert len(RunAuditStore(client.workspace).list())==1
    with pytest.raises(ValueError):
        save_report_document(ctx,'# Reporte',dict(client_id='foreign'))
