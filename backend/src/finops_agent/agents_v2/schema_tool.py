from typing import Any
from langchain_core.tools import tool
from ..engine.schema import COLUMNS
from .registry import definitions,ORCHESTRATOR


def schema_tool(ctx: Any) -> Any:
    @tool
    def get_schema() -> dict[str, Any]:
        """Read actual FOCUS columns, available date range, client profile and registered team IDs."""
        from ..sources.remote_config import read_remote
        source = read_remote(ctx.client)
        if source:
            import json
            path = ctx.client.workspace/'remote-schema.json'
            actual = json.loads(path.read_text())['columns'] if path.exists() else []
            return ctx.record('get_schema',dict(table='focus_data_table',client_id=ctx.client.profile.client_id,
                columns={k:v for k,v in COLUMNS.items() if k.lower() in {c.lower() for c in actual}},normalized_optional_columns=list(COLUMNS),available_from=str(source.available_start),available_to=str(source.available_end),row_count=None,
                mode='remote',focus_version=source.focus_version,validation='Declared range; queries validate actual schema.',
                profile=ctx.client.profile.model_dump(mode='json'),specialists=[dict(id=k,name=v['original_name']) for k,v in definitions().items() if k!=ORCHESTRATOR]))
        with ctx.client.engine.lock:
            span = ctx.client.engine.conn.execute('SELECT min(ChargePeriodStart),max(ChargePeriodEnd),count(*) FROM focus_usage WHERE client_id=?',[ctx.client.profile.client_id]).fetchone()
        return ctx.record('get_schema',dict(table='focus_data_table',client_id=ctx.client.profile.client_id,
            columns=COLUMNS,available_from=str(span[0]),available_to=str(span[1]),row_count=span[2],
            profile=ctx.client.profile.model_dump(mode='json'),specialists=[dict(id=k,name=v['original_name']) for k,v in definitions().items() if k!=ORCHESTRATOR]))
    return get_schema
