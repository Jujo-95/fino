"""Read-only inventory; never run tools, synchronize sources or expose credentials."""
from datetime import datetime,timezone
from typing import Any,cast
from .routes import router,Container
from ..agents_v2.tools import finance_tools,history_tools
from ..chat.tools import ticket_tools,change_tools,billing_tools,ToolContext


@router.get('/clients/{client_id}/connections')
def connection_inventory(client_id: str, c: Container) -> dict[str,Any]:
    client = c.client(client_id)
    from ..sources.remote_config import read_remote
    remote = read_remote(client)
    with client.engine.lock:
        rows = client.engine.conn.execute('SELECT file_name,row_count,ingested_at_utc FROM ingested_batches WHERE client_id=? ORDER BY ingested_at_utc DESC',[client_id]).fetchall()
    documents = [dict(name=path.name,updated_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat())
        for path in sorted((client.workspace/'context_notes').glob('*.md')) if path.is_file() and not path.is_symlink()]
    context = cast(ToolContext,None)
    tools = [*finance_tools(None),*history_tools(None),*ticket_tools(context),*change_tools(context),billing_tools(context)[-1]]
    return dict(client_id=client_id,imports=[dict(name=row[0],rows=row[1],updated_at=str(row[2])) for row in rows],
        documents=documents,tools=[dict(name=tool.name) for tool in tools],external_mcp_supported=False,
        remote_source=remote.model_dump(mode='json') if remote else None)
