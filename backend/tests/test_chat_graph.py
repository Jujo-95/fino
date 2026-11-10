import json
from uuid import uuid4
import pytest
from finops_agent.chat.store import ChatStore
from finops_agent.chat.models import ChatMessage, ResumeRequest
from finops_agent.chat.jobs import ChatJobs
from test_chat_operations import ops as operations_fixture


class ModelDouble:
    model = 'explicit-local-test-double'

    def __init__(self, direct=False):
        self.calls = 0
        self.direct = direct

    async def complete(self, messages, tools):
        self.calls += 1
        context = json.loads(messages[0]['content'].split('BACKEND CONTEXT:\n')[1])
        if context['application_results']:
            result = context['application_results'][-1]
            return dict(message=dict(role='assistant',content='Cambio confirmado.' if result['status']=='applied' else 'Propuesta descartada.'))
        last = messages[-1]
        if last['role']=='user':
            name,args = 'get_tickets',dict(ticket_ids=['FIN-001'])
        elif last.get('name')=='get_tickets':
            ticket = json.loads(last['content'])['tickets'][0]
            name = 'plan_ticket_changes'
            args = dict(changes=[dict(ticket_id='FIN-001',expected_revision=ticket['revision'],
                target_status='APPROVED',append_note='Owner approved',reason='Explicit test decision')])
        else:
            return dict(message=dict(role='assistant',content='FIN-001 requiere revisión.'))
        return dict(message=dict(role='assistant',content='',tool_calls=[dict(id=uuid4().hex,type='function',
            function=dict(name=name,arguments=json.dumps(args)))]))


async def wait_job(container,thread):
    await container.chat.tasks['acme:'+thread['thread_id']]
    return ChatStore(container.client('acme')).read(thread['thread_id'])


@pytest.mark.asyncio
async def test_checkpoint_pause_resume_and_committed_feedback(container):
    ops = operations_fixture.__wrapped__(container)
    container.llm = ModelDouble()
    store = ChatStore(container.client('acme'))
    thread = store.create()
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Revisa FIN-001',message_id=uuid4().hex))
    waiting = await wait_job(container,thread)
    assert waiting['status']=='waiting'
    assert ops.tickets(['FIN-001'])[0]['status']=='PROPOSED'
    assert [a['tool'] for a in waiting['activity']].count('get_tickets') == 1
    container.chat = ChatJobs(container)  # Durable checkpoint survives replacing the job manager.
    approval = ResumeRequest(decision='approve',plan_ids=[waiting['pending'][0]['plan_id']],message_id=uuid4().hex)
    container.chat.start('acme',thread['thread_id'],approval)
    ready = await wait_job(container,thread)
    assert ready['status']=='ready', ready.get('error')
    assert ready['messages'][-1]['content']=='Cambio confirmado.'
    assert ready['changed'] and ops.tickets(['FIN-001'])[0]['status']=='APPROVED'
    assert [a['tool'] for a in ready['activity']].count('get_tickets') == 1
    count = container.llm.calls
    assert container.chat.start('acme',thread['thread_id'],approval)['status']=='ready'
    assert container.llm.calls == count


@pytest.mark.asyncio
@pytest.mark.parametrize('direct',[True,False])
async def test_explicit_order_applies_once_or_proposal_can_be_rejected(container,direct):
    ops = operations_fixture.__wrapped__(container)
    container.llm = ModelDouble()
    store = ChatStore(container.client('acme'))
    thread = store.create()
    text = 'mueve FIN-001 a aprobado porque Owner approved' if direct else 'Qué hago hoy con FIN-001'
    container.chat.start('acme',thread['thread_id'],ChatMessage(text=text,message_id=uuid4().hex))
    result = await wait_job(container,thread)
    if direct:
        assert result['status']=='ready',result.get('error')
        assert ops.tickets(['FIN-001'])[0]['status']=='APPROVED'
    else:
        assert result['status']=='waiting',result.get('error')
        container.chat.start('acme',thread['thread_id'],ResumeRequest(decision='reject',
            plan_ids=[result['pending'][0]['plan_id']],message_id=uuid4().hex))
        result = await wait_job(container,thread)
        assert result['status']=='ready',result.get('error')
        assert ops.tickets(['FIN-001'])[0]['status']=='PROPOSED'


@pytest.mark.asyncio
async def test_missing_provider_is_explicit_error_without_fallback(container):
    thread = ChatStore(container.client('acme')).create()
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Qué hago hoy',message_id=uuid4().hex))
    result = await wait_job(container,thread)
    assert result['status']=='error' and 'NVIDIA' in result['error']
    assert result['messages'][0]['content']=='Qué hago hoy'
    container.llm = ModelDouble()
    operations_fixture.__wrapped__(container)
    container.chat.start('acme',thread['thread_id'],None)
    result = await wait_job(container,thread)
    assert result['status']=='waiting',result.get('error')


@pytest.mark.asyncio
async def test_resume_after_commit_before_checkpoint_does_not_repeat_write(container,monkeypatch):
    ops = operations_fixture.__wrapped__(container)
    container.llm = ModelDouble()
    store = ChatStore(container.client('acme'))
    thread = store.create()
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Revisa FIN-001',message_id=uuid4().hex))
    waiting = await wait_job(container,thread)
    original = ChatStore.activity
    failed = False
    def failure_once(self,thread_id,name,result):
        nonlocal failed
        if name=='apply_ticket_changes' and not failed:
            failed = True
            raise OSError('Explicit failure after durable commit')
        return original(self,thread_id,name,result)
    monkeypatch.setattr(ChatStore,'activity',failure_once)
    container.chat.start('acme',thread['thread_id'],ResumeRequest(decision='approve',
        plan_ids=[waiting['pending'][0]['plan_id']],message_id=uuid4().hex))
    broken = await wait_job(container,thread)
    assert broken['status']=='error'
    assert ops.tickets(['FIN-001'])[0]['status']=='APPROVED'
    container.chat.start('acme',thread['thread_id'],None)
    ready = await wait_job(container,thread)
    assert ready['status']=='ready',ready.get('error')
    assert ready['messages'][-1]['content']=='Cambio confirmado.'
    assert len(ops.tickets(['FIN-001'])[0]['note_history'])==1
