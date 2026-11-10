"""Read cursors for the current local actor; never mutate conversation chronology."""
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from ..config import atomic_write_text
from ..agents.audit_trace import timestamp
from .store import ChatStore


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message_id: str = Field(min_length=1,max_length=200)


def receipt_path(store: ChatStore, thread_id: str) -> Any:
    return store.directory/'read-receipts'/store.path(thread_id).name


def read_state(store: ChatStore, thread: dict[str,Any]) -> dict[str,Any]:
    path = receipt_path(store,thread['thread_id'])
    receipt = json.loads(path.read_text()) if path.exists() else {}
    messages = thread['messages']
    cursor = next((i for i,m in enumerate(messages) if m['id']==receipt.get('message_id')),-1)
    turns = {m.get('turn_id') or m['id'] for m in messages[cursor+1:] if m['role']=='ai' and m.get('content')}
    return dict(unread_count=len(turns),last_read_message_id=receipt.get('message_id'))


def mark_read(client: Any, thread_id: str, message_id: str) -> dict[str,Any]:
    store = ChatStore(client)
    with store.lock:
        thread = store.read(thread_id)
        positions = {m['id']:i for i,m in enumerate(thread['messages']) if m['role']=='ai' and m.get('content')}
        if message_id not in positions:
            raise ValueError('La respuesta no existe en esta conversación.')
        state = read_state(store,thread)
        if positions[message_id]>positions.get(state['last_read_message_id'],-1):
            atomic_write_text(receipt_path(store,thread_id),json.dumps(dict(message_id=message_id,
                actor='local-user',read_at=timestamp())))
        return read_state(store,thread)


def needs_attention(client: Any, thread: dict[str,Any], ticket_ids: list[str], tickets: list[Any] | None = None) -> bool:
    if thread['status']=='waiting':
        return True
    from ..consulting.progress import attention
    return any(t.ticket_id in ticket_ids and attention(t.model_dump(mode='json'))['kind']=='decision'
               for t in (client.tickets.list() if tickets is None else tickets))
