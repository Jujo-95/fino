from contextlib import asynccontextmanager
import os
from collections.abc import AsyncIterator
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from finops_agent.api.spa import SPAStaticFiles
from ..config import ROOT
from .admission import AdmissionError
from ..agents.provider_errors import ProviderError
from ..engine.report_guard import ReportConfirmationRequired
from .container import AppContainer
from .routes import router
from ..chat.routes import router as chat_router
from . import runtime_routes as runtime_routes
from . import source_routes as source_routes
from . import provider_routes as provider_routes
from . import control_routes as control_routes
from . import connections as connections
from . import analysis_routes as analysis_routes
from ..consulting.routes import router as consulting_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from ..agents import runtime_config
    runtime_config.load()
    app.state.container = AppContainer()
    import asyncio
    if os.getenv('FINOPS_ANALYSIS_WORKER_MODE', 'embedded') != 'external':
        app.state.container.jobs.analysis.worker = asyncio.create_task(app.state.container.jobs.analysis.loop())
    try:
        yield
    finally:
        await app.state.container.jobs.shutdown()
        await app.state.container.chat.shutdown()
        app.state.container.close()


app = FastAPI(title="FinOps Agent Console", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(chat_router)
app.include_router(consulting_router)


@app.exception_handler(AdmissionError)
async def admission_error(request: Request, exc: AdmissionError) -> JSONResponse:
    return JSONResponse(status_code=429,content=dict(detail=str(exc),code='local_rate_limit'),
                        headers={'Retry-After':str(exc.retry_after)})


@app.exception_handler(ProviderError)
async def provider_error(request: Request, exc: ProviderError) -> JSONResponse:
    return JSONResponse(status_code=503,content=dict(detail=str(exc),provider_error=exc.public()),
                        headers={'Retry-After':str(max(1,int(exc.retry_after)))})


@app.exception_handler(ReportConfirmationRequired)
async def report_confirmation(request: Request, exc: ReportConfirmationRequired) -> JSONResponse:
    return JSONResponse(status_code=409,content=dict(detail=exc.detail))


@app.exception_handler(ValueError)
async def validation_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(KeyError)
async def missing_resource(request: Request, exc: KeyError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


frontend = ROOT / "frontend/dist"
if frontend.exists():
    app.mount("/", SPAStaticFiles(directory=frontend, html=True), name="frontend")
