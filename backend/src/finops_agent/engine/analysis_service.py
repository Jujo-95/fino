"""Deterministic measurements and native findings, without mandatory model narration."""
import hashlib
import json
import threading
from typing import Any
from collections.abc import Callable
from ..agents.recommendations import recommendations
from ..agents.specs import SPECIALIST_SPECS
from ..consulting.store import ConsultingStore
from ..sources.remote_config import read_remote,schedule
from .analysis_store import latest_analysis,timestamp
from .ticket_triage import mark_attention


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def run_analysis(container: Any, body: Any, identity: str, stop: threading.Event, progress: Callable[[str],None] = lambda stage:None) -> dict[str,Any]:
    client = container.client(body.client_id)
    from ..sources.execution import stop_event
    stop_event.set(stop)
    previous = latest_analysis(client)
    check(stop)
    progress('Revisando fuentes e indicadores')
    remote = read_remote(client)
    if remote:
        from ..sources.remote_analytics import analyze_remote
        overview = analyze_remote(client,body.period_start_utc,body.period_end_utc)
    else:
        overview = container.overview(body.client_id,body.period_start_utc,body.period_end_utc,capture=True)
    check(stop)
    progress('Comparando contexto y decisiones anteriores')
    context = ConsultingStore(client).context()
    source_key = fingerprint([{k:v for k,v in q.items() if k in ('sql','parameters','source_revision')} for q in overview.get('query_evidence',[])]+[overview['actual'],overview['daily']])
    key = analysis_key(client,source_key,context)
    if previous and previous.get('analysis_key')==key and not any(t.status in ('MONITORING','IMPLEMENTED')
            and t.ticket_kind=='finding' for t in client.tickets.list()):
        return dict(previous,run_id=identity,analysis_id=identity,status='skipped',actions=[],skip_reason='Sin cambios de datos, contexto o tareas pendientes.',created_at_utc=timestamp())
    result = dict(schema_version=1,analysis_id=identity,run_id=identity,client_id=body.client_id,
        trigger='schedule' if body.scheduled else 'manual',status='completed',analysis_key=key,
        source_revision=source_key,context_revision=context.get('revision'),policy_revision=fingerprint(client.profile.model_dump()),
        query_catalog_version='base-aggregates-v1',period=dict(start=body.period_start_utc,end=body.period_end_utc),
        created_at_utc=timestamp(),overview=overview,measurements=overview['metrics'],evidence=overview.get('query_evidence',[]),
        findings=[],actions=[],coverage=[],limitations=['Las consultas internas no certifican conformidad FOCUS ni conciliación con factura.'])
    collect_findings(client,result,identity,stop,not body.scheduled or schedule(client).create_tasks)
    check(stop)
    progress('Guardando análisis y tareas')
    result['analysis_key'] = analysis_key(client,source_key,context)
    from .analysis_finalize import finalize
    finalize(client,result,not body.scheduled or schedule(client).create_tasks)
    return result


def analysis_key(client: Any, source_key: str, context: Any) -> str:
    return fingerprint([source_key,context,client.profile.model_dump(),
        [(t.ticket_id,t.status,t.followup,t.resolution_note,t.tags) for t in client.tickets.list()]])


def check(stop: threading.Event) -> None:
    if stop.is_set():
        raise InterruptedError('Análisis detenido por el usuario.')


def collect_findings(client: Any, result: dict[str,Any], identity: str, stop: threading.Event, create: bool) -> None:
    for key,spec in SPECIALIST_SPECS.items():
        check(stop)
        overview = result['overview']
        measured = {m['key']:m['value'] for m in overview['metrics']}
        ready = measured.get(spec.kpi_keys[0]) is not None
        ready = ready and (key!='anomaly' or overview['observed_days']>=4)
        ready = ready and (key!='budgeting' or bool(overview.get('budget_confirmed')))
        findings = recommendations(spec,overview) if ready else []
        if not ready:
            result['status'] = 'partial'
        result['coverage'].append(dict(specialty=key,status='executed' if ready else 'insufficient_data',method='deterministic',model_calls=0))
        for finding in findings:
            result['findings'].append(dict(finding.model_dump(),evidence_refs=[q.get('query_id',q.get('name')) for q in result['evidence']]))
            if not create:
                continue
            with client.engine.lock:
                old = client.tickets.find_existing(finding)
                ticket = client.tickets.create(finding)
                changed = old is None or old.kpi_value!=finding.kpi_value or old.status in ('RESOLVED','IMPLEMENTED')
                if changed:
                    mark_attention(client,ticket,identity,'Nuevo hallazgo medido.' if old is None else 'El indicador cambió; revisa la evidencia.',old is None)
                result['actions'].append(dict(ticket_id=ticket.ticket_id,action='created' if old is None else 'evaluated',changed=changed))
    from ..consulting.followup import followups
    for observation in followups(client,refresh=True):
        check(stop)
        result.setdefault('followups',[]).append(observation)
        ticket = next(t for t in client.tickets.list() if t.ticket_id==observation['ticket_id'])
        from .analysis_followup import refresh_observation
        refresh_observation(client,ticket,observation,identity)
    from .analysis_followup import reevaluate
    reevaluate(client,result,identity)
