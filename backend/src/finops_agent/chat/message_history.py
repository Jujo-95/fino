"""Keep a cancelled tool round from leaving invalid tool-call pairs in the next turn."""
from typing import Any
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage


def complete_history(messages: list[Any]) -> list[Any]:
    last_user = max((i for i,m in enumerate(messages) if isinstance(m,HumanMessage)),default=-1)
    obsolete = {m.tool_call_id for i,m in enumerate(messages) if i<last_user and isinstance(m,ToolMessage)
        and m.name=='save_report' and m.status=='error'}
    answered = {m.tool_call_id for m in messages if isinstance(m,ToolMessage)}-obsolete
    result = []
    for message in messages:
        if isinstance(message,ToolMessage) and message.tool_call_id in obsolete:
            continue
        if isinstance(message,AIMessage) and message.tool_calls:
            calls = [call for call in message.tool_calls if call['id'] in answered]
            message = message.model_copy(update={'tool_calls':calls})
            if not calls and not message.content:
                continue
        result.append(message)
    return result


async def keep_partial(container: Any, store: Any, thread_id: str) -> None:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from .graph import build_chat_graph
    from .jobs import public_messages
    thread = store.read(thread_id)
    preview = thread.get('streaming')
    if not preview or not preview.get('content'):
        return
    config = dict(configurable={'thread_id':thread_id})
    path = str(store.client.workspace/'storage/chat-checkpoints.sqlite')
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = build_chat_graph(container,store.client.profile.client_id,thread_id,thread['turn_id'],saver)
        partial = AIMessage(id=preview['id'],content=preview['content'],additional_kwargs=dict(interrupted=True))
        await graph.aupdate_state(config,dict(messages=[partial]),as_node='model')
        snapshot = await graph.aget_state(config)
    thread = store.read(thread_id)
    thread.update(messages=public_messages(snapshot.values['messages']),streaming=None)
    store.save(thread)
