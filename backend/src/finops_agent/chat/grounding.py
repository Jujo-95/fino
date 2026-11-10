"""Authoritative, tenant-scoped state read before Fino answers; no LLM guessing."""
from typing import Any
from ..agents.audit_trace import timestamp
from ..agents_v2.registry import ORCHESTRATOR
from ..consulting.store import ConsultingStore
from ..engine.incremental_inputs import digest
from .operations import TicketOperations
from ..consulting.ticket_lifecycle import task_presentation


def verified_state(store: Any, thread: dict[str,Any]) -> dict[str,Any] | None:
    if thread.get('agent_id')!=ORCHESTRATOR:
        return None
    try:
        with store.lock:
            context = ConsultingStore(store.client).context()
            refs = list(dict.fromkeys([*([thread['ticket_id']] if thread.get('ticket_id') else []),*thread.get('ticket_refs',[])]))
            tickets = TicketOperations(store.client).tickets(refs) if refs else []
            snapshot = dict(status='verified',client_id=store.client.profile.client_id,read_at=timestamp(),
                confirmed_context=dict(values=context['values'],revision=context['revision'],confirmed_at=context.get('confirmed_at')),
                tickets=[{**{k:t.get(k) for k in ('ticket_id','title','status','workflow_key','resolution_note','revision')},
                          **task_presentation(t)} for t in tickets],
                persistence='Confirmed context is already durable across conversations; no report is required.')
            identity = digest([context['revision'],snapshot['tickets']])
            if not any(a['tool']=='read_confirmed_context' and a['turn_id']==thread['turn_id']
                and a.get('result',{}).get('verification_key')==identity for a in thread['activity']):
                store.activity(thread['thread_id'],'read_confirmed_context',dict(snapshot,verification_key=identity))
            return snapshot
    except Exception:
        snapshot = dict(status='unavailable',client_id=store.client.profile.client_id,
            instruction='No se pudo verificar el estado persistido; no afirmes que se guardó, se perdió o necesita un informe.')
        store.activity(thread['thread_id'],'verify_backend_state',snapshot)
        return snapshot
