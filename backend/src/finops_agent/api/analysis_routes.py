"""Tenant-scoped source setup, metadata discovery and scheduling."""
from datetime import datetime,timezone
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel,Field,ConfigDict
from .routes import router,Container
from ..config import atomic_write_text
from ..sources.remote_config import RemoteSource,AnalysisSchedule,read_remote,save_remote,schedule
from ..engine.analysis_store import latest_analysis
from ..engine.run_audit import RunAuditStore


class SourceSetup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: RemoteSource
    credentials: dict[str,str] | None = Field(default=None,max_length=5)


@router.get('/clients/{client_id}/analysis/settings')
def settings(client_id: str, c: Container) -> dict[str,Any]:
    client = c.client(client_id)
    source = read_remote(client)
    config = schedule(client)
    latest = latest_analysis(client)
    return dict(source=source.model_dump(mode='json') if source else None,schedule=config.model_dump(),
        last_analysis={k:latest.get(k) for k in ('analysis_id','status','created_at_utc','period')} if latest else None,next_run=next_run(config))


def next_run(config: AnalysisSchedule) -> str | None:
    if not config.enabled:
        return None
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    now = datetime.now(timezone.utc).astimezone(ZoneInfo(config.timezone))
    due = now.replace(hour=config.hour,minute=config.minute,second=0,microsecond=0)
    return (due if due>now else due+timedelta(days=1)).astimezone(timezone.utc).isoformat()


@router.put('/clients/{client_id}/analysis/source')
def configure_source(client_id: str, body: SourceSetup, c: Container) -> dict[str,Any]:
    client = c.client(client_id)
    if any(row['status'] in ('running','queued') for row in RunAuditStore(client.workspace).list()):
        raise HTTPException(409,'Detén o espera el análisis antes de cambiar su fuente.')
    if body.credentials:
        from ..sources.remote_credentials import secret
        secret(client,body.source.kind,body.credentials)
    save_remote(client,body.source.model_copy(update={'verified_at':None}))
    (client.workspace/'remote-schema.json').unlink(missing_ok=True)
    return dict(configured=True,credentials_returned=False)


@router.delete('/clients/{client_id}/analysis/source')
def local_source(client_id: str, c: Container) -> dict[str,Any]:
    client = c.client(client_id)
    if any(row['status'] in ('running','queued') for row in RunAuditStore(client.workspace).list()):
        raise HTTPException(409,'Espera o detén el análisis antes de desconectar la fuente.')
    (client.workspace/'remote-source.json').unlink(missing_ok=True)
    (client.workspace/'remote-schema.json').unlink(missing_ok=True)
    atomic_write_text(client.workspace/'analysis-schedule.json',AnalysisSchedule().model_dump_json())
    return dict(mode='local',schedule_enabled=False)


@router.get('/clients/{client_id}/analysis/objects')
def discover(client_id: str, c: Container, offset: int = 0, limit: int = 40) -> dict[str,Any]:
    if offset<0 or offset>10000 or not 1<=limit<=100:
        raise ValueError('Paginación fuera de límites.')
    client = c.client(client_id)
    source = read_remote(client)
    if source is None:
        raise ValueError('Configura primero la fuente remota.')
    try:
        if source.kind=='bigquery':
            from ..sources.bigquery_remote import BigQueryRemote
            remote = BigQueryRemote(client,source,'','')
            try:
                rows = [dict(name=source.table,format='BigQuery',columns=remote.columns,version=remote.revision)]
            finally:
                remote.close()
        else:
            from ..sources.remote_listing import objects
            rows = objects(client,source,str(source.available_start),str(source.available_end))
        save_remote(client,source.model_copy(update={'verified_at':datetime.now(timezone.utc).isoformat()}))
        return dict(objects=rows[offset:offset+limit],next_offset=offset+limit if len(rows)>offset+limit else None,
            validation='Solo acceso y metadatos comprobados; no certifica conformidad FOCUS.',total=len(rows))
    except Exception as exc:
        raise HTTPException(422,'No se pudo acceder al origen. Comprueba identidad, permisos y ubicación ('+type(exc).__name__+').') from None


@router.put('/clients/{client_id}/analysis/schedule')
def save_schedule(client_id: str, body: AnalysisSchedule, c: Container) -> dict[str,Any]:
    client = c.client(client_id)
    source = read_remote(client)
    if body.enabled and source and not source.verified_at:
        raise ValueError('Comprueba primero el acceso a la fuente con «Explorar».')
    if body.use_llm:
        raise ValueError('El job base no utiliza modelos; consulta con el equipo para interpretar sus resultados.')
    atomic_write_text(client.workspace/'analysis-schedule.json',body.model_dump_json())
    return dict(schedule=body.model_dump(),next_run=next_run(body))


@router.post('/clients/{client_id}/tickets/{ticket_id}/reviewed')
def reviewed(client_id: str, ticket_id: str, c: Container) -> dict[str,Any]:
    from ..engine.ticket_triage import review
    return review(c.client(client_id),ticket_id)
