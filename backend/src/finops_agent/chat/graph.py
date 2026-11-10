import json
import asyncio
from typing import Any
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from .tools import chat_tools
from .live import StreamPreview, observe_tools
from .operations import TicketOperations
from .store import ChatStore
from .presentation import public_plan
from .authorization import authorized_directly
from .report_delivery import check_submission_failures
from .model_inputs import prepare_inputs

MAX_MODEL_ROUNDS = 40
GRAPH_RECURSION_LIMIT = MAX_MODEL_ROUNDS * 3 + 5


class ChatState(MessagesState):
    rounds: int
    action_results: list[dict[str, Any]]


def model_node(container: Any, store: ChatStore, thread_id: str, tools: list[Any]) -> Any:
    async def respond(state: ChatState) -> dict[str, Any]:
        if state.get('rounds', 0) >= MAX_MODEL_ROUNDS:
            return dict(messages=[AIMessage(content='Llegué al límite de esta consulta. No aplicaré cambios adicionales; podemos continuar con un alcance más concreto.')])
        if container.llm is None or not hasattr(container.llm, 'complete'):
            raise ValueError('El chat necesita el proveedor NVIDIA configurado; no se usa una respuesta simulada.')
        thread = check_submission_failures(store,thread_id)
        attempts = [a for a in thread['activity'] if a['turn_id']==thread['turn_id'] and
                    (a['tool']=='ticket_proposal_error' or
                     (a['tool']=='plan_ticket_changes' and isinstance(a['result'],dict) and a['result'].get('plan_id')))]
        if len(attempts)>=2 and all(a['tool']=='ticket_proposal_error' for a in attempts[-2:]):
            return dict(messages=[AIMessage(content='No pude preparar el cambio. Ningún ticket fue modificado; inténtalo de nuevo o revisa el estado y los requisitos del ticket.')])
        messages = await asyncio.to_thread(prepare_inputs,store,thread,state)
        preview = StreamPreview(store,thread_id)
        async with container.llm_semaphore:
            schemas = [convert_to_openai_tool(t) for t in tools]
            response = await container.llm.stream_complete(messages,schemas,preview.append) if hasattr(container.llm,'stream_complete') else await container.llm.complete(messages,schemas)
        message = response['message']
        if message.get('content'):
            preview.text = message['content']
            preview.flush()
        calls = [dict(id=c['id'], name=c['function']['name'], args=json.loads(c['function']['arguments']), type='tool_call')
                 for c in message.get('tool_calls', [])]
        if len(calls)>4 or sum(call['name']=='plan_ticket_changes' for call in calls)>1:
            raise ValueError('Máximo cuatro herramientas por ronda del chat.')
        store.activity(thread_id, 'model_response', dict(usage=response.get('usage'), model=response.get('model',getattr(container.llm,'model',None)),fallback=response.get('fallback'),fallback_reason=response.get('fallback_reason')))
        return dict(messages=[AIMessage(id=preview.message_id,content=message.get('content') or '', tool_calls=calls,additional_kwargs={'provider_content':message['provider_content']} if message.get('provider_content') else {})], rounds=state.get('rounds',0)+1)
    return respond


def approval_node(ops: TicketOperations, store: ChatStore, thread_id: str, turn_id: str) -> Any:
    def approve(state: ChatState) -> dict[str, Any]:
        thread = store.read(thread_id)
        ids = {a['result']['plan_id'] for a in thread['activity'] if a['turn_id']==turn_id
               and a['tool']=='plan_ticket_changes' and a['result'].get('plan_id')}
        plans = [ops.read(key, thread_id) for key in sorted(ids)]
        pending = [plan for plan in plans if plan['status']=='pending']
        results = list(state.get('action_results', []))
        for plan in plans:
            receipt = ops.receipt(plan['plan_id'],thread_id)
            if receipt and not any(r.get('plan_id')==plan['plan_id'] for r in results):
                results.append(receipt)
        for plan in pending:
            if authorized_directly(plan, thread):
                auth = dict(actor='local-user', message_id=turn_id)
            else:
                decision = interrupt(dict(plans=[public_plan(plan)], message='Revisa este cambio antes de aplicarlo.'))
                thread = store.read(thread_id)
                if decision.get('plan_ids') != [plan['plan_id']] or thread.get('resume_message_id') != decision.get('message_id'):
                    raise ValueError('La autorización no corresponde a esta propuesta.')
                if decision['decision']=='reject':
                    ops.reject(plan['plan_id'],thread_id)
                    results.append(dict(plan_id=plan['plan_id'],status='rejected'))
                    continue
                auth = dict(actor='local-user', message_id=decision['message_id'])
            try:
                result = ops.apply(plan['plan_id'],thread_id,plan['plan_id'],auth)
            except ValueError as error:
                ops.invalidate(plan['plan_id'])
                result = dict(plan_id=plan['plan_id'],status='conflict',message=str(error))
            results.append(result)
            store.activity(thread_id,'apply_ticket_changes',result)
        return dict(action_results=results)
    return approve


def build_chat_graph(container: Any, client_id: str, thread_id: str, turn_id: str, saver: Any) -> Any:
    store = ChatStore(container.client(client_id))
    tools = chat_tools(container, client_id, thread_id, turn_id)
    graph = StateGraph(ChatState)
    graph.add_node('model', model_node(container,store,thread_id,tools))
    graph.add_node('tools', ToolNode(tools, handle_tool_errors=True,awrap_tool_call=observe_tools(store,thread_id)))
    graph.add_node('approval', approval_node(TicketOperations(container.client(client_id)),store,thread_id,turn_id))
    graph.add_edge(START,'model')
    graph.add_conditional_edges('model', tools_condition)
    graph.add_edge('tools','approval')
    graph.add_edge('approval','model')
    return graph.compile(checkpointer=saver)
