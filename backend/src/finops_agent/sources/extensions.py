"""Only official signed DuckDB extensions, scoped to the application workspace."""
from typing import Any
import duckdb


def load(conn: Any, name: str, client: Any) -> None:
    if name not in ('httpfs','azure'):
        raise ValueError('Extensión no autorizada.')
    try:
        conn.execute('LOAD '+name)
    except duckdb.IOException:
        path = client.workspace.parent/'.duckdb-extensions'
        path.mkdir(exist_ok=True)
        conn.execute("SET extension_directory='"+str(path).replace("'","''")+"'")
        conn.execute('INSTALL '+name+' FROM core')
        conn.execute('LOAD '+name)
