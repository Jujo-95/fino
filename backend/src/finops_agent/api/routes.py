from datetime import datetime, timezone, timedelta
from typing import Annotated, Any, cast
from collections.abc import AsyncIterator
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile
from .run_stream import audit_events
from ..engine.run_audit import RunAuditStore
from ..models import ClientProfile, RunRequest, TicketUpdate
from .container import AppContainer
from .uploads import ingest_uploads, save_upload
from .onboarding import readiness

router = APIRouter(prefix="/api/v1")


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


Container = Annotated[AppContainer, Depends(get_container)]


@router.get("/health")
def health(c: Container) -> dict[str, Any]:
    return {"status": "ok", "duckdb": True, "context_documents": len(c.memory.kb),
            "provider": (c.llm.readiness()["provider"] + " · " + ("configurada" if c.llm.readiness()["configured"] else "sin clave"))
            if hasattr(c.llm, "readiness") else ("mock" if c.llm is None else type(c.llm).__name__)}


@router.get("/clients")
def clients(c: Container) -> list[dict[str, Any]]:
    return [c.client(path.parent.name).profile.model_dump() for path in c.workspaces.glob("*/client_profile.yaml")]


@router.post("/clients/onboard")
async def onboard(request: Request, c: Container) -> dict[str, Any]:
    if "application/json" in request.headers.get("content-type", ""):
        profile = ClientProfile.model_validate(await request.json())
        client = c.onboard(profile)
        return {"client": client.profile.model_dump(), "ingested_rows": 0}
    form = await request.form()
    profile = ClientProfile.model_validate_json(str(form["profile"]))
    client = c.onboard(profile)
    files = [item for item in form.getlist("files") if isinstance(item, StarletteUploadFile)]
    rows = await ingest_uploads(client, files)
    notes = [item for item in form.getlist("notes") if isinstance(item, StarletteUploadFile)]
    for note in notes:
        path = await save_upload(note, client.workspace / "context_notes", ".md")
        client.tickets.index_context("note:" + path.name, path.read_text())
    return {"client": profile.model_dump(), "ingested_rows": rows}


@router.post("/clients/{client_id}/uploads")
async def upload(client_id: str, c: Container, files: list[UploadFile] = File(...)) -> dict[str, int]:
    from ..sources.remote_config import read_remote
    if read_remote(c.client(client_id)):
        raise ValueError('Activa el modo local en Conexiones antes de importar CSV. La fuente remota no se replica.')
    return {"ingested_rows": await ingest_uploads(c.client(client_id), files)}


@router.get("/clients/{client_id}/overview")
def overview(client_id: str, c: Container, start: str | None = None, end: str | None = None) -> dict[str, Any]:
    if start and end:
        validate_period(start, end)
    return c.overview(client_id, start, end)


@router.get("/clients/{client_id}/onboarding")
def onboarding(client_id: str, c: Container) -> dict[str, Any]:
    return readiness(c.client(client_id))


@router.get("/clients/{client_id}/tickets")
def tickets(client_id: str, c: Container, status: str | None = None,
            capability: str | None = None) -> list[dict[str, Any]]:
    from ..engine.ticket_provenance import historical_contributors
    client = c.client(client_id)
    from ..consulting.workflow import sync_tasks
    sync_tasks(client)
    from ..consulting.ticket_lifecycle import task_presentation
    return [{**t, **task_presentation(t)} for t in historical_contributors(client.tickets.list(status, capability), client.workspace)]


@router.patch("/clients/{client_id}/tickets/{ticket_id}")
def update_ticket(client_id: str, ticket_id: str, update: TicketUpdate, c: Container) -> dict[str, Any]:
    from uuid import uuid4
    from ..chat.operations import TicketOperations
    from ..chat.models import PlanRequest
    ops = TicketOperations(c.client(client_id))
    old = ops.tickets([ticket_id])[0]
    message_id = uuid4().hex
    fields = dict(snoozed_until=update.snoozed_until.isoformat()) if update.snoozed_until else None
    plan = ops.plan(PlanRequest.model_validate(dict(changes=[dict(ticket_id=ticket_id, expected_revision=old['revision'],
        target_status=update.status, fields=fields, evidence_refs=['message:'+message_id],
        append_note=update.resolution_note, reason=update.resolution_note)])), 'manual', message_id)
    return dict(ops.apply(plan['plan_id'],'manual',message_id,
        dict(actor='local-user', message_id=message_id))['tickets'][0])


@router.get('/clients/{client_id}/tickets/{ticket_id}/revision')
def ticket_revision(client_id: str, ticket_id: str, c: Container) -> list[dict[str, Any]]:
    from ..chat.operations import TicketOperations
    return TicketOperations(c.client(client_id)).tickets([ticket_id])


@router.get("/clients/{client_id}/reports")
def reports(client_id: str, c: Container) -> list[dict[str, str]]:
    workspace = c.client(client_id).workspace
    store = RunAuditStore(workspace)
    if any(store.directory.glob("*.json")):
        return store.reports()
    return [{"name": path.name, "markdown": path.read_text()}
            for path in sorted((workspace / "reports").glob("*.md"), reverse=True)]


@router.post("/runs/stream")
async def run(body: RunRequest, request: Request, c: Container) -> StreamingResponse:
    body = prepare_run(body, c)
    record = c.jobs.start(body)
    return StreamingResponse(events(body, request, c,record), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def validate_period(start: str, end: str) -> None:
    first = datetime.fromisoformat(start.replace("Z", "+00:00"))
    last = datetime.fromisoformat(end.replace("Z", "+00:00"))
    if any(value.utcoffset() not in (None, timedelta(0)) for value in (first, last)):
        raise ValueError("Only UTC timestamps are accepted")
    first, last = first.replace(tzinfo=timezone.utc), last.replace(tzinfo=timezone.utc)
    if first >= last or first.day != 1 or (last - first).days > 31:
        raise ValueError("Select a month-to-date period starting on the first day, with an exclusive end")
    if (last.date().replace(day=1) != first.date().replace(day=1)) and last.day != 1:
        raise ValueError("Period must stay within one calendar month")


async def events(body: RunRequest, request: Request, c: AppContainer, record: dict[str,Any] | None = None) -> AsyncIterator[str]:
    async for event in audit_events(body, request, c,record):
        yield event


@router.get("/clients/{client_id}/runs")
def run_history(client_id: str, c: Container) -> list[dict[str, Any]]:
    return RunAuditStore(c.client(client_id).workspace).list()


@router.get("/clients/{client_id}/runs/{run_id}")
def run_detail(client_id: str, run_id: str, c: Container) -> dict[str, Any]:
    from ..chat.report_ticket_links import report_ticket_links
    client = c.client(client_id)
    return {**RunAuditStore(client.workspace).detail(run_id),'ticket_ids':report_ticket_links(client,run_id)}


def prepare_run(body: RunRequest, c: AppContainer) -> RunRequest:
    client = c.client(body.client_id)
    if body.reference_run_id:
        previous = RunAuditStore(client.workspace).read(body.reference_run_id)
        if previous["status"] != "completed":
            raise ValueError("Only a completed report can be revised")
        body = body.model_copy(update={key: previous[key] for key in ("period_start_utc", "period_end_utc")})
    validate_period(body.period_start_utc, body.period_end_utc)
    return body


@router.post('/runs')
async def start_run(body: RunRequest, c: Container) -> dict[str, Any]:
    record = c.jobs.start(prepare_run(body, c))
    return dict(run_id=record['run_id'], client_id=body.client_id, status=record['status'])


@router.get('/clients/{client_id}/runs/{run_id}/events')
async def subscribe_run(client_id: str, run_id: str, c: Container) -> StreamingResponse:
    RunAuditStore(c.client(client_id).workspace).read(run_id)
    async def stream() -> AsyncIterator[str]:
        from .run_stream import frame
        async for event in c.jobs.subscribe(client_id, run_id):
            yield ': heartbeat\n\n' if event['node']=='__heartbeat__' else frame(event['node'], event['payload'], run_id)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control':'no-cache'})
