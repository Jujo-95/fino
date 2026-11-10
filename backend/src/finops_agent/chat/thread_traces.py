"""Persist links on the child; derive parent timeline without synthetic model messages."""
from typing import Any
from ..agents.audit_trace import timestamp
from .store import ChatStore


def link_parent(client: Any, child: dict[str, Any], parent_id: str | None) -> dict[str, Any]:
    if not parent_id:
        return child
    store = ChatStore(client)
    with store.lock:
        parent = store.read(parent_id)
        if parent['client_id']!=client.profile.client_id or parent.get('ticket_id') or parent.get('internal') or parent.get('archived'):
            raise ValueError('Selecciona una conversación principal activa de este cliente.')
        links = dict(child.get('parent_links',{}))
        if parent_id not in links:
            links[parent_id] = dict(after_message_id=parent['messages'][-1]['id'] if parent['messages'] else None,
                                    attached_at=timestamp())
            child['parent_links'] = links
            store.save(child)
    return child


def thread_traces(client: Any, parent_id: str) -> list[dict[str, Any]]:
    store = ChatStore(client)
    traces = []
    with store.lock:
        for path in store.directory.glob('*.json'):
            child = store.read(path.stem)
            link = child.get('parent_links',{}).get(parent_id)
            if not link or not child.get('ticket_id') or child['client_id']!=client.profile.client_id:
                continue
            initial = next((m for m in child['messages'] if m['role']=='human'),None)
            if initial:
                traces.append(dict(thread_id=child['thread_id'],ticket_id=child['ticket_id'],
                    initial_message=initial['content'],initial_message_id=initial['id'],**link))
    return sorted(traces,key=lambda row:(row['attached_at'],row['thread_id']))


def conversation_summary(client: Any, thread: dict[str, Any]) -> dict[str, Any]:
    from .read_receipts import read_state,needs_attention
    store = ChatStore(client)
    traces = thread_traces(client,thread['thread_id'])
    reading = read_state(store,thread)
    reading['unread_count'] += sum(read_state(store,store.read(t['thread_id']))['unread_count'] for t in traces)
    attention = needs_attention(client,thread,list(set(thread.get('ticket_refs',[])+[t['ticket_id'] for t in traces])))
    title = next((str(m['content'])[:70] for m in thread['messages'] if m['role']=='human'),
                 str(traces[0]['initial_message'])[:70] if traces else 'Nueva conversación')
    return dict(thread_id=thread['thread_id'],status=thread['status'],updated_at=thread['updated_at'],
        agent_id=thread.get('agent_id','orchestrator'),empty=not thread['messages'] and not traces,title=title,needs_attention=attention,**reading)
