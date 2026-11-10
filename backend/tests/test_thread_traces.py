from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from finops_agent.chat.store import ChatStore
from finops_agent.chat.ticket_threads import ticket_thread
from finops_agent.chat.thread_traces import thread_traces
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
import test_chat_operations as helpers


@pytest.fixture
def trace_client(container):
    return helpers.ops.__wrapped__(container).client


def start_child(client,parent):
    store=ChatStore(client)
    child=ticket_thread(client,'FIN-001',lambda:None,parent['thread_id'])
    child['messages']=[dict(id=uuid4().hex,role='human',content='Guíame con FIN-001.'),
                       dict(id=uuid4().hex,role='ai',content='Primer paso.',turn_id='first')]
    store.save(child)
    return child


def test_trace_is_persistent_idempotent_and_not_a_second_model_message(trace_client):
    store=ChatStore(trace_client)
    parent=store.create('v2-finops-report-orchestrator')
    parent['messages']=[dict(id='anchor',role='human',content='Revisemos mis tareas.')]
    store.save(parent)
    child=start_child(trace_client,parent)
    for _ in range(3):
        ticket_thread(trace_client,'FIN-001',lambda:None,parent['thread_id'])
    traces=thread_traces(trace_client,parent['thread_id'])
    assert len(traces)==1 and traces[0]['initial_message']=='Guíame con FIN-001.'
    assert traces[0]['after_message_id']=='anchor' and traces[0]['thread_id']==child['thread_id']
    assert store.read(parent['thread_id'])['messages']==parent['messages']
    parent['messages'].append(dict(id='later',role='human',content='Otra consulta'))
    store.save(parent)
    assert thread_traces(trace_client,parent['thread_id'])[0]['after_message_id']=='anchor'


def test_empty_side_thread_does_not_create_a_fake_initial_message(trace_client):
    store=ChatStore(trace_client)
    parent=store.create('v2-finops-report-orchestrator')
    ticket_thread(trace_client,'FIN-001',lambda:None,parent['thread_id'])
    assert thread_traces(trace_client,parent['thread_id'])==[]
    start_child(trace_client,parent)
    summary=store.list()[0]
    assert not summary['empty'] and summary['title']=='Guíame con FIN-001.'
    new=store.get_or_create('v2-finops-report-orchestrator',None,lambda:None)
    assert new['thread_id']!=parent['thread_id']


def test_trace_rejects_foreign_parent_and_nested_ticket_threads(trace_client,container):
    from finops_agent.models import ClientProfile
    container.onboard(ClientProfile(client_id='other',client_name='Other'))
    foreign=ChatStore(container.client('other')).create()
    with pytest.raises(KeyError):
        ticket_thread(trace_client,'FIN-001',lambda:None,foreign['thread_id'])
    child=ticket_thread(trace_client,'FIN-001',lambda:None)
    with pytest.raises(ValueError,match='principal'):
        ticket_thread(trace_client,'FIN-002',lambda:None,child['thread_id'])


def test_http_parent_detail_contains_trace_and_same_shared_reply_count(trace_client,container):
    app.dependency_overrides[get_container]=lambda:container
    try:
        http=TestClient(app)
        base='/api/v1/clients/acme/chat/threads'
        parent=ChatStore(trace_client).create('v2-finops-report-orchestrator')
        response=http.post(base+'/for-ticket/FIN-001',json=dict(parent_thread_id=parent['thread_id']))
        assert response.status_code==200
        child=start_child(trace_client,parent)
        for _ in range(2):
            detail=http.get(base+'/'+parent['thread_id']).json()
            assert detail['messages']==[] and len(detail['ticket_threads'])==1
        summaries=http.get(base+'/ticket-summaries').json()
        assert summaries[0]['reply_count']==1 and summaries[0]['parent_thread_ids']==[parent['thread_id']]
        assert detail['ticket_threads'][0]['thread_id']==child['thread_id']
        assert not container.chat.tasks
    finally:
        app.dependency_overrides.clear()
