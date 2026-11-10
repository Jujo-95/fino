"""Attention is persistent ticket state, independent of chat unread receipts."""
from typing import Any
from .analysis_store import timestamp


def review(client: Any, ticket_id: str) -> dict[str,Any]:
    with client.engine.lock:
        ticket = next((t for t in client.tickets.list() if t.ticket_id==ticket_id),None)
        if ticket is None:
            raise KeyError(ticket_id)
        updated = ticket.model_copy(update={'is_new':False,'reviewed_at_utc':timestamp()})
        return client.tickets._commit(updated).model_dump(mode='json')


def mark_attention(client: Any, ticket: Any, run_id: str, reason: str, is_new: bool = False) -> Any:
    with client.engine.lock:
        return client.tickets._commit(ticket.model_copy(update=dict(is_new=is_new or ticket.is_new,
            needs_attention=True,attention_reason=reason,last_evaluated_run_id=run_id,
            last_evaluated_at=timestamp(),last_changed_analysis_id=run_id)))
