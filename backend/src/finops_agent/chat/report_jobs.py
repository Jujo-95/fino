"""Register the existing server-owned chat task as a first-class report job."""
from typing import Any
from langchain_core.tools import tool
from ..engine.run_audit import RunAuditStore
from ..models import RunRequest
from .report_confirmation import confirm_repeat, repeat_token


def begin_report(ctx: Any) -> dict[str, Any]:
    container = ctx.evidence.container
    thread = ctx.store.read(ctx.thread_id)
    store = RunAuditStore(ctx.client.workspace)
    with ctx.store.lock:
        if thread.get('report_turn_id')==ctx.turn_id and thread.get('report_run_id'):
            return store.read(thread['report_run_id'])
        if any(r['status'] in ('queued','running') for r in store.list()):
            raise ValueError('Ya hay una revisión en curso para este cliente. Espera o deténla desde Análisis.')
        for key,record in container.jobs.records.items():
            if record['client_id']==ctx.client.profile.client_id and not container.jobs.tasks[key].done():
                raise ValueError('Ya hay un informe en curso para este cliente. Consúltalo en Reportes.')
        scope = ctx.evidence.current().state
        body = dict(client_id=ctx.client.profile.client_id,run_mode='daily',billing_currency=ctx.client.profile.billing_currency,
            period_start_utc=scope['period_start_utc'],period_end_utc=scope['period_end_utc'],
            repeat_confirmation=repeat_token(thread))
        from ..engine.report_guard import require_confirmation
        require_confirmation(ctx.client,RunRequest(**body))
        record = container.jobs.analysis.start(RunRequest(**body), as_report=True)
        thread.update(report_run_id=record['run_id'],report_turn_id=ctx.turn_id)
        ctx.store.save(thread)
    return record


def finish_report(container: Any, store: Any, thread_id: str) -> None:
    thread = store.read(thread_id)
    key = thread.get('report_run_id')
    if not key or thread.get('report_turn_id')!=thread.get('turn_id'):
        return
    runs = RunAuditStore(store.client.workspace)
    record = runs.read(key)
    if record.get('agent_generation')!='2.0' or record.get('canonical_engine') == 'analysis':
        return
    if record['status']=='running':
        status = 'cancelled' if thread['status']=='cancelled' else 'failed'
        reason = 'Detenido por el usuario.' if status=='cancelled' else thread.get('error') or 'El análisis terminó sin guardar un informe completo.'
        runs.finish(record,status,reason)
    if key in container.jobs.logs:
        container.jobs.append(runs,key,'__done__' if record['status']=='completed' else '__error__',
            dict(run_id=key,message=record.get('error'),status=record['status']))
    container.jobs.forget(key)


def report_tools(ctx: Any) -> list[Any]:
    @tool
    async def start_report_job() -> dict[str, Any]:
        """Start/register a durable report job BEFORE analyzing a requested report. Progress stays in chat and Reportes. Repeated calls in the same turn reuse its ID."""
        thread = ctx.store.read(ctx.thread_id)
        same_job = thread.get('report_turn_id')==ctx.turn_id and thread.get('report_run_id')
        if not same_job and not confirm_repeat(ctx):
            return ctx.record('start_report_job',dict(status='declined',message='No se creará otro informe. Conserva el existente.'))
        record = begin_report(ctx)
        return ctx.record('start_report_job',dict(run_id=record['run_id'],status=record['status'],
            message='Informe registrado en Reportes. El análisis continúa en segundo plano; no necesitas guardarlo de nuevo.'
            if record.get('canonical_engine') == 'analysis' else 'Informe en ejecución en Reportes; no necesitas consultar su estado repetidamente.'))
    return [start_report_job]


def report_progress(store: Any, thread: dict[str, Any], name: str) -> None:
    key = thread.get('report_run_id')
    if not key or thread.get('report_turn_id')!=thread.get('turn_id') or name=='model_response':
        return
    runs = RunAuditStore(store.client.workspace)
    record = runs.read(key)
    if record.get('agent_generation')!='2.0' or record['status']!='running':
        return
    record['source_activity'] = [a for a in thread['activity'] if a['turn_id']==thread['turn_id']]
    record['last_activity'] = name
    record.setdefault('events',[]).append(dict(node='chat_activity',payload=dict(trace=None,tool=name)))
    runs.save(record)

