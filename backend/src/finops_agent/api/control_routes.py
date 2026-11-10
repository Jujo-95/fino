"""Tenant-scoped emergency cancellation of existing backend tasks."""
from typing import Any
from .routes import router, Container
from ..engine.run_audit import RunAuditStore


@router.post('/clients/{client_id}/runs/{run_id}/stop')
async def stop_report(client_id: str, run_id: str, c: Container) -> dict[str, Any]:
    store = RunAuditStore(c.client(client_id).workspace)
    record = store.read(run_id)
    if (record.get('analysis_only') or record.get('canonical_engine') == 'analysis') \
            and c.jobs.analysis.stop(client_id,run_id):
        return store.read(run_id)
    if record['status']!='running':
        return record
    if record.get('agent_generation')=='2.0' and record.get('thread_id'):
        await c.chat.stop(client_id,record['thread_id'])
        return store.read(run_id)
    task = c.jobs.tasks.get(run_id)
    store.finish(record,'cancelled','Detenido por el usuario.')
    if task and not task.done():
        task.cancel('user-stop')
        import asyncio
        await asyncio.gather(task,return_exceptions=True)
    return store.read(run_id)
