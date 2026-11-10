from typing import Any
from langchain_core.tools import tool
from ..engine.schema import COLUMNS
from .registry import definitions, use_cases
from .sql import query
from .snapshots import execute_case, read_snapshots


def window(ctx: Any, start: str | None, end: str | None) -> tuple[str,str]:
    if bool(start)!=bool(end):
        raise ValueError('Proporciona ambas fechas para comparar otro periodo.')
    scope = ctx.evidence.current().state
    return start or scope['period_start_utc'],end or scope['period_end_utc']

def finance_tools(ctx: Any) -> list[Any]:
    from .schema_tool import schema_tool
    get_schema = schema_tool(ctx)
    @tool
    def query_finance(sql: str, start_utc: str | None = None, end_utc: str | None = None, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute read-only DuckDB SELECT on focus_data_table. Client/currency enforced. Optional [start,end) historical window; named parameters only."""
        return ctx.record('query_finance',query(ctx.client,sql,*window(ctx,start_utc,end_utc),parameters))
    @tool
    def get_data_preview(limit: int = 5) -> dict[str, Any]:
        """Read up to 20 actual rows within the current client and reporting period."""
        if not 1<=limit<=20:
            raise ValueError('Máximo 20 filas.')
        return ctx.record('get_data_preview',query(ctx.client,'SELECT '+','.join(COLUMNS)+f' FROM focus_data_table LIMIT {limit}',*window(ctx,None,None)))
    @tool
    def get_use_case(use_case_id: int) -> dict[str, Any]:
        """Read imported reference use case including original SQL; inspect schema before adapting."""
        if use_case_id not in use_cases():
            raise ValueError('Use case desconocido.')
        return ctx.record('get_use_case',use_cases()[use_case_id])
    @tool
    def execute_use_case(use_case_id: int, start_utc: str | None = None, end_utc: str | None = None, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a reference use case with safe SQL/date adaptation. Missing columns/parameters are not zeros."""
        return ctx.record('execute_use_case',execute_case(ctx.client,use_case_id,*window(ctx,start_utc,end_utc),parameters))
    @tool
    def read_use_case_snapshots(use_case_ids: list[int] | None = None) -> dict[str, Any]:
        """Read/materialize persisted current-period reference use-case results. Defaults to this role's cases, or all 60 for orchestrator."""
        ids = use_case_ids if use_case_ids is not None else definitions()[ctx.store.read(ctx.thread_id)['agent_id']]['use_case_ids'] or []
        if not ids:
            return ctx.record('read_use_case_snapshots',dict(status='select_scope',message='Read read_analysis first; select explicit use_case_ids or delegate a focused specialty. No automatic execution of all cases.'))
        return ctx.record('read_use_case_snapshots',read_snapshots(ctx.client,*window(ctx,None,None),ids))
    return [get_schema,query_finance,get_data_preview,get_use_case,execute_use_case,read_use_case_snapshots]


def history_tools(ctx: Any) -> list[Any]:
    @tool
    def list_reports(limit: int = 10) -> dict[str, Any]:
        """List completed reports of the active client with IDs and periods, before reading an older report."""
        from ..engine.run_audit import RunAuditStore
        if not 1<=limit<=20:
            raise ValueError('Máximo 20 informes.')
        rows = [row for row in RunAuditStore(ctx.client.workspace).list()
                if row['status']=='completed' and row['client_id']==ctx.client.profile.client_id][:limit]
        return ctx.record('list_reports',dict(client_id=ctx.client.profile.client_id,reports=rows))
    from .analysis_tools import analysis_tools
    return [list_reports,*analysis_tools(ctx)]
