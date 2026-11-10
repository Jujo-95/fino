import re
from typing import Any
from langchain_core.messages import HumanMessage
from .models import ChatMessage
from .operations import TicketOperations
from .authorization import explicit_order
from .agent_context import validate_run


def prepare_message(container: Any, client_id: str, thread: dict[str, Any], body: ChatMessage) -> dict[str, Any]:
    client = container.client(client_id)
    validate_run(client,body.audit_run_id)
    if thread['status'] in ('waiting','error'):
        raise ValueError('Primero resuelve la propuesta pendiente o reanuda la consulta interrumpida.')
    refs = list(dict.fromkeys([*([thread['ticket_id']] if thread.get('ticket_id') else []),*body.ticket_refs,*re.findall(r'\bFIN-\d+\b',body.text.upper())]))
    if refs:
        TicketOperations(client).tickets(refs)
    thread['messages'].append(dict(id=body.message_id,role='human',content=body.text))
    thread.update(activity_anchor=body.message_id,turn_id=body.message_id,user_text=body.text,ticket_refs=refs,
                  direct_order=explicit_order(body.text),pending=[],changed=False)
    if body.audit_run_id:
        thread['audit_run_id'] = body.audit_run_id
    return dict(messages=[HumanMessage(content=body.text,id=body.message_id)],rounds=0,action_results=[])
