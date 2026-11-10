import json
from langchain_core.messages import ToolMessage
from .report_delivery import saved_receipt, check_submission_failures
from time import monotonic
from typing import Any
from uuid import uuid4
from .store import ChatStore


class StreamPreview:
    def __init__(self, store: ChatStore, thread_id: str) -> None:
        self.store,self.thread_id = store,thread_id
        self.message_id,self.text,self.last_write = uuid4().hex,'',0.0

    async def append(self, text: str) -> None:
        self.text += text
        if monotonic()-self.last_write >= .1:
            self.flush()

    def flush(self) -> None:
        with self.store.lock:
            thread = self.store.read(self.thread_id)
            thread['activity_anchor'] = self.message_id
            thread['streaming'] = dict(id=self.message_id,content=self.text,turn_id=thread['turn_id'])
            self.store.save(thread)
        self.last_write = monotonic()


def observe_tools(store: ChatStore, thread_id: str) -> Any:
    async def observe(request: Any, execute: Any) -> Any:
        call = request.tool_call
        if call['name']=='save_report' and (receipt:=saved_receipt(store,thread_id)):
            store.activity(thread_id,'save_report',receipt)
            return ToolMessage(content=json.dumps(receipt),tool_call_id=call['id'],name='save_report')
        store.working(thread_id,call['id'],call['name'],True)
        try:
            result = await execute(request)
            if call['name'] in ('plan_ticket_changes','propose_ticket_transition') and isinstance(result, ToolMessage):
                text = str(result.content)
                if result.status == 'error' or text.startswith('Propuesta no registrada'):
                    store.activity(thread_id, 'ticket_proposal_error', dict(error='No se pudo validar la propuesta.'))
            if getattr(result,'status',None)=='error':
                store.activity(thread_id,call['name'],dict(error=str(result.content)))
                if call['name']=='save_report':
                    check_submission_failures(store,thread_id)
            return result
        finally:
            store.working(thread_id,call['id'],call['name'],False)
    return observe
