import asyncio
import json
from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..api.routes import Container
from .models import ChatMessage, ResumeRequest, ThreadRequest, ArchiveRequest, TicketThreadRequest
from .store import ChatStore
from .read_receipts import ReadRequest,mark_read,read_state

router = APIRouter(prefix='/api/v1/clients/{client_id}/chat/threads')


@router.get('')
async def threads(client_id: str, c: Container, agent_id: str | None = None, archived: bool = False) -> list[dict[str, Any]]:
    rows = ChatStore(c.client(client_id)).list(agent_id,archived)
    return [{**row,'status':'error'} if row['status']=='running' and client_id+':'+row['thread_id'] not in c.chat.tasks else row for row in rows]


@router.get('/ticket-summaries')
async def ticket_summaries(client_id: str, c: Container) -> list[dict[str, Any]]:
    from .ticket_threads import ticket_thread_summaries
    return ticket_thread_summaries(c.client(client_id),set(c.chat.tasks))


@router.post('/for-ticket/{ticket_id}')
async def open_ticket_thread(client_id: str, ticket_id: str, c: Container, body: TicketThreadRequest | None = None) -> dict[str, Any]:
    from .ticket_threads import ticket_thread
    thread = ticket_thread(c.client(client_id),ticket_id,
        lambda: c.request_limits.admit('threads:'+client_id,20,0,1),body.parent_thread_id if body else None)
    return await detail(client_id,thread['thread_id'],c)


@router.post('')
async def create_thread(client_id: str, c: Container, body: ThreadRequest | None = None) -> dict[str, Any]:
    body = body or ThreadRequest()
    return ChatStore(c.client(client_id)).get_or_create(
        body.agent_id,body.audit_run_id,lambda: c.request_limits.admit('threads:'+client_id,20,0,1))


@router.patch('/{thread_id}/archive')
async def archive_thread(client_id: str, thread_id: str, body: ArchiveRequest, c: Container) -> dict[str, Any]:
    client = c.client(client_id)
    store = ChatStore(client)
    with store.lock:
        store.read(thread_id)
        if client_id+':'+thread_id in c.chat.tasks:
            raise HTTPException(status_code=409,detail='Espera a que termine la respuesta antes de archivar la conversación.')
        return store.set_archived(thread_id,body.archived)


@router.get('/{thread_id}')
async def detail(client_id: str, thread_id: str, c: Container) -> dict[str, Any]:
    store = ChatStore(c.client(client_id))
    with store.lock:
        thread = store.read(thread_id)
        reading = read_state(store,thread)
    if thread['status']=='running' and client_id+':'+thread_id not in c.chat.tasks:
        thread = {**thread, 'status':'error', 'error':'La conversación se interrumpió; puedes reanudarla.'}
    from .thread_traces import thread_traces
    return {**thread,**reading,'ticket_threads':thread_traces(c.client(client_id),thread_id)}


@router.patch('/{thread_id}/read')
async def read_conversation(client_id: str, thread_id: str, body: ReadRequest, c: Container) -> dict[str,Any]:
    return mark_read(c.client(client_id),thread_id,body.message_id)


@router.post('/{thread_id}/messages')
async def message(client_id: str, thread_id: str, body: ChatMessage, c: Container) -> dict[str, Any]:
    return c.chat.start(client_id,thread_id,body)


@router.post('/{thread_id}/resume')
async def resume(client_id: str, thread_id: str, body: ResumeRequest, c: Container) -> dict[str, Any]:
    return c.chat.start(client_id,thread_id,body)


@router.post('/{thread_id}/stop')
async def stop(client_id: str, thread_id: str, c: Container) -> dict[str, Any]:
    return await c.chat.stop(client_id,thread_id)


@router.post('/{thread_id}/retry')
async def retry(client_id: str, thread_id: str, c: Container) -> dict[str, Any]:
    return c.chat.start(client_id,thread_id,None)


@router.get('/{thread_id}/events')
async def events(client_id: str, thread_id: str, c: Container) -> StreamingResponse:
    store = ChatStore(c.client(client_id))
    store.read(thread_id)
    async def stream() -> Any:
        stamp = ''
        while True:
            thread = await detail(client_id,thread_id,c)
            if thread['updated_at'] != stamp:
                stamp = thread['updated_at']
                yield 'data: '+json.dumps(thread,ensure_ascii=False)+'\n\n'
            else:
                yield ': heartbeat\n\n'
            if thread['status'] != 'running':
                return
            await asyncio.sleep(.15)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache'})


@router.get('/{thread_id}/operations')
async def operation_history(client_id: str, thread_id: str, c: Container) -> list[dict[str, Any]]:
    from .operations import TicketOperations
    client = c.client(client_id)
    ChatStore(client).read(thread_id)
    TicketOperations(client)
    with client.engine.lock:
        rows = client.engine.conn.execute('SELECT document FROM ticket_commands WHERE thread_id=?', [thread_id]).fetchall()
    return [json.loads(row[0]) for row in rows]
