import json
from uuid import uuid4
import pytest
from finops_agent.chat.tools import ToolContext,change_tools
from finops_agent.chat.models import Change,ChatMessage
from finops_agent.chat.store import ChatStore
from finops_agent.agents_v2.registry import ORCHESTRATOR
from test_agents_v2_flow import call
from test_chat_graph import wait_job
from test_ticket_report_bridge import new_finding
from test_chat_operations import ops as operations_fixture


def test_missing_finding_returns_actionable_feedback_not_exception(container):
    store=ChatStore(container.client('acme'))
    thread=store.create(ORCHESTRATOR)
    ctx=ToolContext(container,'acme',thread['thread_id'],'test')
    tool=change_tools(ctx)[0]
    result=tool.invoke(dict(changes=[dict(action='create',reason='SECRET fixture reason',evidence_refs=['query:test']*20)]))
    assert 'finding como objeto' in result and 'kpi_value' in result
    assert 'SECRET' not in result and 'ToolInvocationError' not in result
    assert not ctx.client.tickets.list()
    assert not ctx.client.engine.conn.execute('SELECT * FROM ticket_change_plans').fetchall()


def test_evidence_duplicates_are_removed_before_limit_validation():
    change=Change(ticket_id='FIN-001',expected_revision='a'*64,reason='Evidence',append_note='Note',
        evidence_refs=['query:first','query:second']*20)
    assert change.evidence_refs==['query:first','query:second']
    with pytest.raises(ValueError):
        Change(ticket_id='FIN-001',expected_revision='a'*64,reason='Evidence',append_note='Note',
            evidence_refs=[f'query:{i}' for i in range(21)])


@pytest.mark.asyncio
async def test_graph_recovers_from_missing_finding_without_writing_ticket(container,csv_path):
    ops=operations_fixture.__wrapped__(container)
    ops.client.engine.ingest_focus_csv('acme',csv_path)
    finding=new_finding(ops)
    class Model:
        async def complete(self,messages,tools):
            last=messages[-1]
            if last['role']=='user':
                return call('plan_ticket_changes',dict(changes=[dict(action='create',reason='Measured allocation finding')]))
            if last.get('name')=='plan_ticket_changes':
                assert 'finding como objeto' in last['content']
                return call('query_finance',dict(sql='SELECT sum(EffectiveCost) AS cost FROM focus_data_table'))
            data=json.loads(last['content'])
            return call('plan_ticket_changes',dict(changes=[dict(action='create',finding=finding,
                reason='Measured allocation finding',evidence_refs=[data['evidence_id']])]))
    container.llm=Model()
    store=ChatStore(ops.client)
    thread=store.create(ORCHESTRATOR)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Crea un ticket',message_id=uuid4().hex))
    waiting=await wait_job(container,thread)
    assert waiting['status']=='waiting',waiting.get('error')
    assert len(waiting['pending'])==1 and len(ops.client.tickets.list())==2
    assert waiting['pending'][0]['changes'][0]['finding']['title']==finding['title']
