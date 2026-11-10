import pytest
from fastapi.testclient import TestClient
from finops_agent.chat.store import ChatStore
from finops_agent.chat.ticket_threads import ticket_thread,ticket_thread_summaries
from finops_agent.chat.read_receipts import mark_read,read_state
from finops_agent.chat.thread_traces import conversation_summary
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.models import ClientProfile,TicketUpdate
import test_chat_operations as helpers


@pytest.fixture
def client(container):
    return helpers.ops.__wrapped__(container).client


def answered(client):
    store=ChatStore(client)
    thread=ticket_thread(client,'FIN-001',lambda:None)
    thread['messages']=[dict(id='human',role='human',content='Ayúdame'),
        dict(id='a',role='ai',content='Paso uno',turn_id='turn-1'),
        dict(id='b',role='ai',content='Paso dos',turn_id='turn-1')]
    store.save(thread)
    return store,thread


def test_receipt_survives_store_reload_without_reordering_or_resolving_ticket(client):
    store,thread=answered(client)
    before=store.read(thread['thread_id'])
    assert read_state(store,thread)['unread_count']==1
    assert mark_read(client,thread['thread_id'],'a')['unread_count']==1
    assert mark_read(client,thread['thread_id'],'b')['unread_count']==0
    assert ChatStore(client).read(thread['thread_id'])==before
    summary=ticket_thread_summaries(client,set())[0]
    assert summary['unread_count']==0 and not summary['needs_attention']
    assert next(t for t in client.tickets.list() if t.ticket_id=='FIN-001').status=='PROPOSED'


def test_old_ack_cannot_swallow_new_response_or_move_cursor_backwards(client):
    store,thread=answered(client)
    mark_read(client,thread['thread_id'],'b')
    thread['messages'].append(dict(id='c',role='ai',content='Nueva información',turn_id='turn-2'))
    store.save(thread)
    assert mark_read(client,thread['thread_id'],'a')==dict(unread_count=1,last_read_message_id='b')
    assert mark_read(client,thread['thread_id'],'c')['unread_count']==0
    assert mark_read(client,thread['thread_id'],'c')['unread_count']==0


def test_foreign_and_unknown_responses_cannot_be_acknowledged(client,container):
    store,thread=answered(client)
    container.onboard(ClientProfile(client_id='other',client_name='Other'))
    with pytest.raises(KeyError):
        mark_read(container.client('other'),thread['thread_id'],'a')
    for message_id in ('human','nonexistent'):
        with pytest.raises(ValueError):
            mark_read(client,thread['thread_id'],message_id)
    assert read_state(store,thread)['unread_count']==1


def test_parent_shows_child_unread_but_reading_parent_does_not_read_child(client):
    store,child=answered(client)
    parent=store.create('v2-finops-report-orchestrator')
    ticket_thread(client,'FIN-001',lambda:None,parent['thread_id'])
    assert conversation_summary(client,parent)['unread_count']==1
    assert not conversation_summary(client,parent)['needs_attention']
    mark_read(client,child['thread_id'],'b')
    assert conversation_summary(client,parent)['unread_count']==0
    assert not conversation_summary(client,parent)['needs_attention']
    client.tickets.update('FIN-001',TicketUpdate(status='RESOLVED',resolution_note='Validado'))
    assert not conversation_summary(client,parent)['needs_attention']


def test_read_route_is_explicit_and_get_never_marks_read(client,container):
    store,thread=answered(client)
    app.dependency_overrides[get_container]=lambda:container
    try:
        http=TestClient(app)
        url='/api/v1/clients/acme/chat/threads/'+thread['thread_id']
        assert http.get(url).json()['unread_count']==1
        assert http.get(url).json()['unread_count']==1
        assert http.patch(url+'/read',json=dict(message_id='b')).json()['unread_count']==0
        assert http.get(url).json()['unread_count']==0
        assert http.patch(url+'/read',json=dict(message_id='not-real')).status_code==422
        assert not container.chat.tasks
    finally:
        app.dependency_overrides.clear()
