"""One durable worker extends RunJobs and its audit/SSE/cancel channels."""
import asyncio
import threading
from time import perf_counter
from datetime import datetime,timedelta,timezone
from typing import Any
from zoneinfo import ZoneInfo
from ..models import RunRequest
from ..engine.analysis_queue import AnalysisQueue
from ..engine.analysis_service import run_analysis
from ..engine.run_audit import RunAuditStore
from ..sources.remote_config import schedule,read_remote


class AnalysisJobs:
    def __init__(self, jobs: Any) -> None:
        self.jobs = jobs
        self.queue = AnalysisQueue(jobs.container.workspaces)
        self.worker: asyncio.Task[None] | None = None
        self.stops: dict[str,threading.Event] = {}
        self.closing = False

    def start(self, body: RunRequest, key: str | None = None, as_report: bool = False) -> dict[str,Any]:
        store = RunAuditStore(self.jobs.container.client(body.client_id).workspace)
        active = next((r for r in store.list() if r['status'] in ('running','queued')),None)
        if active:
            record = store.read(active['run_id'])
            if as_report and record.get('analysis_only'):
                record.update(analysis_only=False, canonical_engine='analysis')
                store.save(record)
                self.queue.promote_report(record['run_id'])
            return record
        from uuid import uuid4
        payload = {**body.model_dump(), '_canonical_report': as_report}
        identity,created = self.queue.enqueue(payload,key or 'manual:'+uuid4().hex)
        if created:
            record = store.create({**body.model_dump(),'run_id':identity},'deterministic')
            record.update(status='queued',analysis_only=not as_report,analysis_id=identity,
                          agent_generation='2.0',canonical_engine='analysis')
            store.save(record)
        else:
            record = store.read(identity)
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self.loop(),name='finops-analysis-worker')
        return record

    async def loop(self) -> None:
        while True:
            ran = await self.run_once()
            if not ran:
                await asyncio.sleep(5)

    async def run_once(self) -> bool:
        self.tick(datetime.now(timezone.utc))
        row = self.queue.claim()
        if not row:
            return False
        await self.execute(row)
        return True

    async def execute(self, row: dict[str,Any]) -> None:
        identity = row['id']
        payload = row['body']
        as_report = bool(payload.pop('_canonical_report', False))
        body = RunRequest.model_validate(payload)
        store = RunAuditStore(self.jobs.container.client(body.client_id).workspace)
        try:
            record = store.read(identity)
        except KeyError:
            record = store.create({**body.model_dump(),'run_id':identity},'deterministic')
            record.update(analysis_only=not as_report,analysis_id=identity,agent_generation='2.0',
                          canonical_engine='analysis')
        record.update(status='running',error=None,attempts=row['attempts']+1)
        store.save(record)
        self.jobs.records[identity],self.jobs.logs[identity] = record,[]
        stop = self.stops[identity] = threading.Event()
        started = perf_counter()
        try:
            def progress(stage: str) -> None:
                self.jobs.append(store,identity,'analysis_step',dict(message=stage))
            task = asyncio.create_task(asyncio.to_thread(run_analysis,self.jobs.container,body,identity,stop,progress))
            self.jobs.tasks[identity] = task
            result = await asyncio.shield(task)
            if stop.is_set():
                raise InterruptedError('Detenido')
            record['analysis'] = result
            if as_report:
                from ..engine.analysis_report import render_analysis
                record['report_markdown'] = render_analysis(result)
                record['report_file'] = identity + '.md'
                atomic = self.jobs.container.client(body.client_id).workspace / 'reports'
                atomic.mkdir(parents=True, exist_ok=True)
                from ..config import atomic_write_text
                atomic_write_text(atomic / (identity + '.md'), record['report_markdown'])
            record['statistics'] = dict(duration_ms=round((perf_counter()-started)*1000),llm_calls=0,tokens=0,
                queries=len(result.get('evidence',[])),cache_hits=sum(bool(q.get('cache_hit')) for q in result.get('evidence',[])))
            record['queries'] = result.get('evidence',[])
            store.finish(record,result['status'])
            self.queue.update(identity,result['status'],'saved')
            self.jobs.append(store,identity,'__done__',{'analysis_id':identity})
        except (asyncio.CancelledError,InterruptedError):
            await self.cancelled(identity,store,record,stop,task)
        except Exception as exc:
            self.failed(row,store,record,exc)
        finally:
            self.stops.pop(identity,None)
            self.jobs.forget(identity)

    async def cancelled(self, identity: str, store: Any, record: Any, stop: threading.Event, task: Any) -> None:
        stop.set()
        await asyncio.gather(task,return_exceptions=True)
        saved = self.queue.get(identity)
        cancelled = bool(saved and saved['state']=='cancelled')
        state = 'queued' if self.closing and not cancelled else 'cancelled'
        store.finish(record,state,'Se retomará después del reinicio.' if state=='queued' else 'Análisis detenido; no se programarán más consultas.')
        self.queue.update(identity,state)
        if self.closing:
            raise asyncio.CancelledError

    def failed(self, row: dict[str,Any], store: Any, record: dict[str,Any], exc: Exception) -> None:
        from ..sources.execution import SourceError
        if isinstance(exc,SourceError) and exc.transient and row['attempts']<2:
            self.queue.retry(row['id'],row['attempts'])
            record.update(status='queued',error='La fuente está temporalmente ocupada; reintento acotado pendiente.')
            store.save(record)
        else:
            store.finish(record,'failed','No se pudo consultar la fuente. Revisa credenciales, permisos, esquema y límites ('+type(exc).__name__+').')
            self.queue.update(row['id'],'failed',type(exc).__name__)
            self.jobs.append(store,row['id'],'__error__',{'message':record['error']})

    def stop(self, client_id: str, identity: str) -> bool:
        row = self.queue.get(identity)
        if not row or row['client']!=client_id:
            return False
        self.queue.update(identity,'cancelled')
        if identity in self.stops:
            self.stops[identity].set()
        store = RunAuditStore(self.jobs.container.client(client_id).workspace)
        store.finish(store.read(identity),'cancelled','Detenido por el usuario; la consulta actual puede tardar hasta su límite en detenerse.')
        return True

    def tick(self, now: datetime) -> None:
        for path in self.jobs.container.workspaces.glob('*/analysis-schedule.json'):
            client = self.jobs.container.client(path.parent.name)
            config = schedule(client)
            local = now.astimezone(ZoneInfo(config.timezone))
            due = local.replace(hour=config.hour,minute=config.minute,second=0,microsecond=0)
            if not config.enabled or local<due:
                continue
            key = 'schedule:'+client.profile.client_id+':'+str(due.date())
            if self.queue.has_key(key):
                continue
            source = read_remote(client)
            cutoff = (local-timedelta(days=config.latency_days)).date()
            if source:
                cutoff = min(cutoff,source.available_end)
            else:
                with client.engine.lock:
                    latest = client.engine.conn.execute('SELECT max(ChargePeriodStart) FROM focus_usage WHERE client_id=?',[client.profile.client_id]).fetchone()
                if latest and latest[0]:
                    cutoff = min(cutoff,latest[0].date()+timedelta(days=1))
            start = cutoff.replace(day=1)
            if source:
                start = max(start,source.available_start)
            if start<cutoff:
                self.start(RunRequest(client_id=client.profile.client_id,period_start_utc=str(start),
                    period_end_utc=str(cutoff),analysis_only=True,scheduled=True),key)

    async def shutdown(self) -> None:
        self.closing = True
        for stop in self.stops.values():
            stop.set()
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker,return_exceptions=True)
        self.queue.close()
