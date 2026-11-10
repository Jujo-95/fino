"""Server-owned jobs. HTTP subscriptions never own or cancel execution."""
import asyncio
import json
from typing import Any
from collections.abc import AsyncIterator
from ..config import atomic_write_text
from ..engine.run_audit import RunAuditStore
from ..models import RunRequest


class RunJobs:
    def __init__(self, container: Any) -> None:
        self.container = container
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.records: dict[str, dict[str, Any]] = {}
        self.logs: dict[str, list[dict[str, Any]]] = {}
        from .analysis_jobs import AnalysisJobs
        self.analysis = AnalysisJobs(self)
        from .analysis_recovery import recover
        recover(self)

    def start(self, body: RunRequest) -> dict[str, Any]:
        from ..engine.report_guard import require_confirmation
        if not body.analysis_only:
            require_confirmation(self.container.client(body.client_id), body)
        return self.analysis.start(body, as_report=not body.analysis_only)

    def forget(self, run_id: str) -> None:
        self.tasks.pop(run_id, None)
        self.records.pop(run_id, None)
        self.logs.pop(run_id, None)

    def append(self, store: RunAuditStore, run_id: str, node: str, payload: dict[str, Any]) -> None:
        self.logs[run_id].append(dict(node=node, payload=payload, run_id=run_id))
        path = store.directory / 'events' / (run_id+'.json')
        atomic_write_text(path, json.dumps(self.logs[run_id], default=str))

    async def subscribe(self, client_id: str, run_id: str) -> AsyncIterator[dict[str, Any]]:
        store = RunAuditStore(self.container.client(client_id).workspace)
        record = store.read(run_id)  # Tenant-scoped existence check even for in-memory jobs.
        if record['status'] == 'running' and run_id not in self.tasks and not record.get('analysis_only') \
                and not record.get('canonical_engine'):
            store.finish(record, 'failed', 'El proceso backend anterior se detuvo; esta ejecución quedó interrumpida.')
        cursor = 0
        while True:
            path = store.directory / 'events' / (run_id+'.json')
            log = self.logs.get(run_id) if run_id in self.logs else (json.loads(path.read_text()) if path.exists() else [])
            for event in (log or [])[cursor:]:
                cursor += 1
                yield event
            record = store.read(run_id)
            if record['status'] not in ('running','queued'):
                if not log or log[-1]['node'] not in ('__done__','__error__'):
                    yield dict(node='__done__' if record['status'] in ('completed','partial','skipped') else '__error__',
                               payload={'message':record.get('error')}, run_id=run_id)
                return
            yield dict(node='__heartbeat__', payload={}, run_id=run_id)
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        await self.analysis.shutdown()
        active = [task for task in self.tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
