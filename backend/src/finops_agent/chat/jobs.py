import asyncio
from typing import Any
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from .store import ChatStore
from ..engine.incremental_inputs import digest
from .models import ChatMessage, ResumeRequest
from .graph import build_chat_graph, GRAPH_RECURSION_LIMIT
from .start_inputs import prepare_message


class ChatJobs:
    def __init__(self, container: Any) -> None:
        self.container = container
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, client_id: str, thread_id: str, body: ChatMessage | ResumeRequest | None) -> dict[str, Any]:
        store = ChatStore(self.container.client(client_id))
        thread = store.read(thread_id)
        key = client_id+':'+thread_id
        if replayed(thread,body):
            return thread
        if thread.get('archived'):
            raise ValueError('Restaura la conversación antes de continuar.')
        if key in self.tasks:
            raise ValueError('El orquestador sigue trabajando en esta conversación.')
        self.container.request_limits.admit('chat:'+client_id,12,len(self.tasks),4)
        if isinstance(body, ChatMessage):
            value: Any = prepare_message(self.container,client_id,thread,body)
        elif isinstance(body, ResumeRequest):
            expected = [p['plan_id'] for p in thread['pending']] or [(thread.get('pending_report') or {}).get('confirmation_id')]
            if thread['status']!='waiting' or body.plan_ids != expected:
                raise ValueError('No hay una propuesta pendiente que coincida.')
            thread['resume_message_id'] = body.message_id
            value = Command(resume=body.model_dump())
        else:
            if thread['status'] not in ('error','running') or not thread.get('turn_id'):
                raise ValueError('No hay un trabajo interrumpido para reanudar.')
            value = None
        if body:
            thread['seen_messages'][body.message_id] = digest(body.model_dump())
        thread.update(status='running',error=None,error_detail=None,streaming=None,working_tools=[],stop_requested=False)
        store.save(thread)
        task = asyncio.create_task(self.execute(client_id,thread_id,value), name='finops-chat:'+key)
        self.tasks[key] = task
        task.add_done_callback(lambda completed:self.tasks.pop(key,None))
        return thread

    async def stop(self, client_id: str, thread_id: str) -> dict[str, Any]:
        store = ChatStore(self.container.client(client_id))
        thread = store.read(thread_id)
        task = self.tasks.get(client_id+':'+thread_id)
        if thread['status']!='running':
            return thread
        thread.update(status='cancelled',error=None,error_detail=None,working_tools=[],stop_requested=True)
        store.save(thread)
        if task and not task.done():
            task.cancel('user-stop')
            await asyncio.gather(task,return_exceptions=True)
        from .message_history import keep_partial
        await keep_partial(self.container,store,thread_id)
        from .report_jobs import finish_report
        finish_report(self.container,store,thread_id)
        return store.read(thread_id)

    async def execute(self, client_id: str, thread_id: str, value: Any) -> None:
        client = self.container.client(client_id)
        store = ChatStore(client)
        thread = store.read(thread_id)
        config = dict(configurable={'thread_id':thread_id}, recursion_limit=GRAPH_RECURSION_LIMIT)
        try:
            async with AsyncSqliteSaver.from_conn_string(str(client.workspace/'storage/chat-checkpoints.sqlite')) as saver:
                graph = build_chat_graph(self.container,client_id,thread_id,thread['turn_id'],saver)
                async for _ in graph.astream(value, config, stream_mode='updates'):
                    await self.snapshot(graph,config,store,thread_id)
                await self.snapshot(graph,config,store,thread_id,finished=True)
        except asyncio.CancelledError:
            if store.read(thread_id).get('status')!='cancelled':
                self.failure(store,thread_id,'El backend se detuvo. Puedes reanudar la conversación.')
            raise
        except Exception as error:
            self.failure(store,thread_id,str(error),error.public() if hasattr(error,'public') else None)
        finally:
            from .report_jobs import finish_report
            finish_report(self.container,store,thread_id)

    async def snapshot(self, graph: Any, config: Any, store: ChatStore, thread_id: str, finished: bool = False) -> None:
        snapshot = await graph.aget_state(config)
        thread = store.read(thread_id)
        thread['messages'] = public_messages(snapshot.values.get('messages', []))
        thread['streaming'] = None
        pauses = [i.value for task in snapshot.tasks for i in task.interrupts]
        thread['pending'] = [p for pause in pauses for p in pause.get('plans', [])]
        thread['pending_report'] = next((p for p in pauses if p.get('kind')=='repeat_report'),None)
        report_ready = False
        if thread.get('report_run_id'):
            from ..engine.run_audit import RunAuditStore
            report_ready = RunAuditStore(store.client.workspace).read(thread['report_run_id']).get('status') == 'completed'
        thread['changed'] = report_ready or any(item.get('status')=='applied' for item in snapshot.values.get('action_results', [])) or any(
            a['tool']=='save_report' and a.get('turn_id')==thread['turn_id'] and a['result'].get('status')=='saved' for a in thread['activity'])
        thread['status'] = 'waiting' if pauses else 'ready' if finished else 'running'
        store.save(thread)

    def failure(self, store: ChatStore, thread_id: str, message: str, detail: Any = None) -> None:
        thread = store.read(thread_id)
        thread.update(status='error',error=message,error_detail=detail,working_tools=[])
        store.save(thread)

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


def replayed(thread: dict[str, Any], body: ChatMessage | ResumeRequest | None) -> bool:
    if not body or body.message_id not in thread['seen_messages']:
        return False
    if thread['seen_messages'][body.message_id] != digest(body.model_dump()):
        raise ValueError('Ese identificador ya corresponde a otro mensaje.')
    return True


def public_messages(messages: list[Any]) -> list[dict[str, Any]]:
    result, turn_id = [], None
    for message in messages:
        if message.type=='human':
            turn_id = message.id
        if message.type in ('human','ai') and message.content:
            result.append(dict(id=message.id,role=message.type,content=message.content,turn_id=turn_id,interrupted=message.additional_kwargs.get('interrupted',False)))
    return result
