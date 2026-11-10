import json
from uuid import uuid4
import pytest
from finops_agent.chat.models import ChatMessage, ResumeRequest
from finops_agent.chat.store import ChatStore
from finops_agent.agents_v2.registry import ORCHESTRATOR
from test_chat_graph import wait_job
from test_chat_operations import ops as operations_fixture


def call(name, args):
    return dict(message=dict(role='assistant', content='', tool_calls=[dict(id=uuid4().hex, type='function',
        function=dict(name=name, arguments=json.dumps(args)))]))


@pytest.mark.asyncio
async def test_transition_proposal_requires_approval_and_updates_existing_tickets(container):
    ops = operations_fixture.__wrapped__(container)
    class Model:
        async def complete(self, messages, tools):
            if messages[-1]['role'] == 'user':
                return call('propose_ticket_transition', dict(ticket_ids=['FIN-001','FIN-002'],
                    target_status='APPROVED', reason='Revisados por el usuario'))
            return dict(message=dict(role='assistant',content='Cambios procesados.'))
    container.llm = Model()
    store = ChatStore(ops.client)
    thread = store.create(ORCHESTRATOR)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Propón aprobar estos tickets',message_id=uuid4().hex))
    pending = await wait_job(container,thread)
    assert pending['status']=='waiting', pending.get('error')
    assert all(t['status']=='PROPOSED' for t in ops.tickets(['FIN-001','FIN-002']))
    container.chat.start('acme',thread['thread_id'],ResumeRequest(decision='approve',
        plan_ids=[pending['pending'][0]['plan_id']],message_id=uuid4().hex))
    result = await wait_job(container,thread)
    assert result['status']=='ready', result.get('error')
    assert all(t['status']=='APPROVED' for t in ops.tickets(['FIN-001','FIN-002']))


@pytest.mark.asyncio
async def test_invalid_transition_stops_after_two_attempts(container):
    operations_fixture.__wrapped__(container)
    class Model:
        calls = 0
        async def complete(self, messages, tools):
            self.calls += 1
            return call('plan_ticket_changes',dict(changes=[dict(action='update',ticket_id='FIN-001',
                expected_revision='a'*64,fields=dict(target_status='APPROVED'),reason='revisión')]))
    container.llm = Model()
    store = ChatStore(container.client('acme'))
    thread = store.create(ORCHESTRATOR)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Revisar FIN-001',message_id=uuid4().hex))
    result = await wait_job(container,thread)
    assert result['status']=='ready', result.get('error')
    assert container.llm.calls==2, result['activity'][-5:]
    assert 'Ningún ticket fue modificado' in result['messages'][-1]['content']
