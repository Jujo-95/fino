import asyncio
from typing import Any
from uuid import uuid4
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from ..engine.incremental_inputs import digest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from .registry import definitions, ORCHESTRATOR


async def delegate(ctx: Any, specialist: str, question: str) -> dict[str, Any]:
    parent = ctx.store.read(ctx.thread_id)
    if specialist not in definitions() or specialist==ORCHESTRATOR or not 1<=len(question)<=4000:
        raise ValueError('Selecciona un especialista 2.0 y una tarea acotada.')
    count = sum(a['tool']=='consult_specialist' and a['turn_id']==ctx.turn_id for a in parent['activity'])
    if count>=16:
        raise ValueError('Se alcanzó el límite de delegaciones de este informe.')
    child_id = digest([ctx.thread_id,ctx.turn_id,specialist,question])[:32]
    child = ctx.store.read(child_id) if ctx.store.path(child_id).exists() else ctx.store.create(specialist,parent.get('audit_run_id'),child_id)
    if child.get('internal') and child['status']=='ready':
        return contribution(child,specialist)
    turn = child.get('turn_id') or uuid4().hex
    child.update(internal=True,parent_thread_id=ctx.thread_id,status='running',turn_id=turn,ticket_refs=[],direct_order=None)
    ctx.store.save(child)
    request = question+'\nEntrega solo un JSON con summary (breve), findings (lista de hallazgos con mediciones y referencias), limitations, evidence_refs y next_steps. No incluyas monólogo intermedio. Lee read_analysis antes de ampliar consultas. Solo evidencia real. No modifiques tickets.'
    try:
        result = await run_child(ctx,child,turn,request)
        saved = ctx.store.read(child['thread_id'])
        from ..chat.jobs import public_messages
        saved.update(status='ready',messages=public_messages(result['messages']),streaming=None,working_tools=[])
        ctx.store.save(saved)
    except BaseException as error:
        saved = ctx.store.read(child['thread_id'])
        saved.update(status='cancelled' if isinstance(error,asyncio.CancelledError) else 'error',working_tools=[])
        ctx.store.save(saved)
        raise
    return contribution(saved,specialist)


def contribution(child: dict[str, Any], specialist: str) -> dict[str, Any]:
    from .contribution import deliverable
    return deliverable(child,specialist)


async def run_child(ctx: Any, child: dict[str, Any], turn: str, request: str) -> dict[str, Any]:
    from ..chat.graph import build_chat_graph, GRAPH_RECURSION_LIMIT
    path = str(ctx.client.workspace/'storage/chat-checkpoints.sqlite')
    config = dict(configurable={'thread_id':child['thread_id']},recursion_limit=GRAPH_RECURSION_LIMIT)
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = build_chat_graph(ctx.evidence.container,ctx.client.profile.client_id,child['thread_id'],turn,saver)
        previous = await graph.aget_state(config)
        value = None if previous.values else dict(messages=[HumanMessage(content=request,id=turn)],rounds=0,action_results=[])
        return dict(await graph.ainvoke(value,config))


def orchestrator_tools(ctx: Any) -> list[Any]:
    @tool
    async def consult_specialist(specialist: str, question: str) -> dict[str, Any]:
        """Delegate a focused task to a registered v2 specialist. Returns its original structured deliverable, backed by scoped tools."""
        return ctx.record('consult_specialist',await delegate(ctx,specialist,question))
    return [consult_specialist]
