"""Shared structured inputs and the same backend analysis job used by the UI."""
from typing import Any
from langchain_core.tools import tool
from ..engine.analysis_store import latest_analysis
from ..models import RunRequest


def analysis_tools(ctx: Any) -> list[Any]:
    @tool
    def read_analysis(specialty: str | None = None) -> dict[str,Any]:
        """Read retained current-client measurements, coverage, findings and followups. No cloud scan or model call. Optional capability filter."""
        value = latest_analysis(ctx.client)
        if not value:
            return ctx.record('read_analysis',dict(available=False,next_step='start_analysis_job'))
        keys = ('analysis_id','status','period','source_revision','coverage','limitations','followups')
        data = {key:value.get(key) for key in keys}
        data['measurements'] = [m for m in value['measurements'] if not specialty or m['capability']==specialty]
        data['findings'] = [f for f in value['findings'] if not specialty or f['capability']==specialty][:30]
        return ctx.record('read_analysis',data)
    @tool
    def start_analysis_job() -> dict[str,Any]:
        """Update measured analysis and native task proposals in a persistent backend job; does not generate a narrative report. Returns job ID; do not poll repeatedly."""
        scope = ctx.evidence.current().state
        body = RunRequest(client_id=ctx.client.profile.client_id,analysis_only=True,
            period_start_utc=scope['period_start_utc'],period_end_utc=scope['period_end_utc'])
        value = ctx.evidence.container.jobs.start(body)
        return ctx.record('start_analysis_job',dict(analysis_id=value['run_id'],status=value['status'],
            message='El trabajo continuará en segundo plano. Consulta su resultado en Análisis.'))
    return [read_analysis,start_analysis_job]
