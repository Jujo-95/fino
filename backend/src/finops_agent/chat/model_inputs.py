import json
from typing import Any
from langchain_core.messages import HumanMessage
from .agent_context import instructions,report_context,runtime_details
from .message_history import complete_history
from .provider_messages import provider_messages
from .grounding import verified_state


def prepare_inputs(store: Any, thread: dict[str,Any], state: Any) -> list[dict[str,Any]]:
    context = dict(primary_ticket_id=thread.get('ticket_id'),ticket_refs=thread['ticket_refs'],
        direct_order=thread.get('direct_order'),application_results=state.get('action_results',[]),
        instruction='Usa el estado verificado actual antes de afirmar persistencia o estado de tickets. '
            'Lee tickets adicionales solo si la pregunta lo requiere. Usa append_note exacta de direct_order si existe. '
            'Las operaciones nuevas requieren un recibo aplicado. Usa #FIN-001 para referencias inline.')
    context['verified_state'] = verified_state(store,thread)
    history = complete_history(state['messages'])
    starts = [i for i,message in enumerate(history) if isinstance(message,HumanMessage)]
    recent = history[starts[-4]:] if len(starts)>4 else history
    context['agent_id'] = thread.get('agent_id','orchestrator')
    context.update(runtime_details(store.client,context['agent_id']))
    context['selected_report'] = report_context(store.client,thread)
    specialty = bool(thread.get('internal'))
    return [{'role':'system','content':instructions(context['agent_id'], specialty)+'\nBACKEND CONTEXT:\n'+json.dumps(context,ensure_ascii=False)},
        *provider_messages(recent)]
