"""One durable conversation per client/ticket; opening never starts a model."""
from typing import Any, Callable
from ..engine.incremental_inputs import digest
from ..agents_v2.registry import ORCHESTRATOR
from .store import ChatStore


def ticket_thread(client: Any, ticket_id: str, admit: Callable[[], None], parent_thread_id: str | None = None) -> dict[str, Any]:
    from .thread_traces import link_parent
    store = ChatStore(client)
    with store.lock:
        if not any(t.ticket_id==ticket_id for t in client.tickets.list()):
            raise KeyError('Ticket no encontrado en este cliente.')
        key = digest(['ticket-thread-v1',client.profile.client_id,ticket_id])[:32]
        if store.path(key).exists():
            thread = store.read(key)
            if thread.get('ticket_id')!=ticket_id or thread['client_id']!=client.profile.client_id:
                raise ValueError('La conversación no corresponde al ticket activo.')
            thread = store.set_archived(key,False) if thread.get('archived') else thread
            return link_parent(client,thread,parent_thread_id)
        admit()
        return link_parent(client,store.create(ORCHESTRATOR,thread_id=key,ticket_id=ticket_id),parent_thread_id)


def ticket_thread_summaries(client: Any, active: set[str]) -> list[dict[str, Any]]:
    from .read_receipts import read_state,needs_attention
    store = ChatStore(client)
    ticket_rows = client.tickets.list()
    tickets = {t.ticket_id for t in ticket_rows}
    rows = []
    with store.lock:
        for key in tickets:
            identity = digest(['ticket-thread-v1',client.profile.client_id,key])[:32]
            if not store.path(identity).exists():
                continue
            thread = store.read(identity)
            replies = {m.get('turn_id') or m['id'] for m in thread['messages'] if m['role']=='ai'}
            state = thread['status']
            if state=='running' and client.profile.client_id+':'+identity not in active:
                state = 'error'
            rows.append(dict(ticket_id=key,thread_id=identity,status=state,archived=thread.get('archived',False),
                started=bool(thread['messages'] or thread.get('turn_id')),reply_count=len(replies),
                updated_at=thread['updated_at'],parent_thread_ids=list(thread.get('parent_links',{})),
                needs_attention=needs_attention(client,thread,[key],ticket_rows),**read_state(store,thread)))
    return rows
