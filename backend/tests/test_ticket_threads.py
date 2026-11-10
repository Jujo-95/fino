from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
import asyncio
from fastapi.testclient import TestClient
from finops_agent.chat.ticket_threads import ticket_thread, ticket_thread_summaries
from finops_agent.chat.store import ChatStore
from finops_agent.chat.start_inputs import prepare_message
from finops_agent.chat.models import ChatMessage
from finops_agent.models import ClientProfile
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
import test_chat_operations as helpers


@pytest.fixture
def ticket_client(container):
    return helpers.ops.__wrapped__(container).client


def test_concurrent_open_creates_exactly_one_durable_thread_without_model(ticket_client):
    calls = []
    def open_thread(_):
        return ticket_thread(ticket_client,'FIN-001',lambda:calls.append('admitted'))
    with ThreadPoolExecutor(max_workers=6) as pool:
        threads = list(pool.map(open_thread,range(6)))
    assert len({t['thread_id'] for t in threads})==1 and calls==['admitted']
    thread = threads[0]
    assert thread['ticket_id']=='FIN-001' and thread['ticket_refs']==['FIN-001']
    assert thread['messages']==[] and thread['status']=='ready'
    assert ticket_thread(ticket_client,'FIN-001',lambda:None)['thread_id']==thread['thread_id']
    assert ticket_thread(ticket_client,'FIN-002',lambda:None)['thread_id']!=thread['thread_id']
    assert len(list((ticket_client.workspace/'chat/threads').glob('*.json')))==2


def test_ticket_threads_do_not_replace_generic_empty_conversations(ticket_client):
    store = ChatStore(ticket_client)
    bound = ticket_thread(ticket_client,'FIN-001',lambda:None)
    generic = store.get_or_create('v2-finops-report-orchestrator',None,lambda:None)
    assert bound['thread_id']!=generic['thread_id']
    assert [t['thread_id'] for t in store.list()]==[generic['thread_id']]
    store.set_archived(bound['thread_id'],True)
    restored = ticket_thread(ticket_client,'FIN-001',lambda:None)
    assert restored['thread_id']==bound['thread_id'] and not restored['archived']


def test_binding_is_pinned_on_every_message_and_counts_turns(ticket_client,container):
    thread = ticket_thread(ticket_client,'FIN-001',lambda:None)
    prepare_message(container,'acme',thread,ChatMessage(text='¿Qué sigue?',message_id=uuid4().hex))
    assert thread['ticket_refs']==['FIN-001']
    turn = thread['turn_id']
    thread['messages'].extend([dict(id=uuid4().hex,role='ai',content='Paso uno',turn_id=turn),
                               dict(id=uuid4().hex,role='ai',content='Resultado',turn_id=turn)])
    thread['status']='running'
    ChatStore(ticket_client).save(thread)
    active = {'acme:'+thread['thread_id']}
    summary = ticket_thread_summaries(ticket_client,active)[0]
    assert summary['started'] and summary['reply_count']==1 and summary['status']=='running'
    assert ticket_thread_summaries(ticket_client,set())[0]['status']=='error'


def test_same_ticket_id_in_other_client_has_separate_thread(ticket_client,container):
    container.onboard(ClientProfile(client_id='other',client_name='Other'))
    other = container.client('other')
    source = ticket_client.tickets.list()[0]
    from finops_agent.models import Finding
    other.tickets.create(Finding.model_validate(source.model_dump()))
    first = ticket_thread(ticket_client,'FIN-001',lambda:None)
    second = ticket_thread(other,'FIN-001',lambda:None)
    assert first['thread_id']!=second['thread_id']
    assert ticket_thread_summaries(other,set())[0]['thread_id']==second['thread_id']
    with pytest.raises(KeyError):
        ChatStore(other).read(first['thread_id'])


def test_http_open_reuses_thread_and_summaries_do_not_start_jobs(ticket_client,container):
    app.dependency_overrides[get_container]=lambda:container
    try:
        http = TestClient(app)
        base = '/api/v1/clients/acme/chat/threads'
        first = http.post(base+'/for-ticket/FIN-001')
        assert first.status_code==200
        assert http.post(base+'/for-ticket/FIN-001').json()['thread_id']==first.json()['thread_id']
        summary = http.get(base+'/ticket-summaries')
        assert summary.status_code==200 and summary.json()[0]['reply_count']==0
        assert not summary.json()[0]['started'] and not container.chat.tasks
        assert http.post(base+'/for-ticket/FIN-999').status_code==404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reopening_active_ticket_keeps_original_backend_job(ticket_client,container):
    from test_chat_graph import wait_job
    entered,release = asyncio.Event(),asyncio.Event()
    class PendingDouble:
        calls = 0
        async def complete(self,messages,tools):
            self.calls+=1
            entered.set()
            await release.wait()
            return dict(message=dict(role='assistant',content='Seguimos en el mismo hilo.'))
    container.llm=PendingDouble()
    thread=ticket_thread(ticket_client,'FIN-001',lambda:None)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Ayúdame.',message_id=uuid4().hex))
    await entered.wait()
    original=container.chat.tasks['acme:'+thread['thread_id']]
    reopened=ticket_thread(ticket_client,'FIN-001',lambda:None)
    assert reopened['thread_id']==thread['thread_id'] and reopened['status']=='running'
    assert container.chat.tasks['acme:'+thread['thread_id']] is original
    release.set()
    ready=await wait_job(container,thread)
    assert ready['status']=='ready' and container.llm.calls==1
    assert ticket_thread_summaries(ticket_client,set())[0]['reply_count']==1
