"""One scoped relation, reused by agents and deterministic analytics."""
from typing import Any
import json
import sqlglot
from sqlglot import exp
from .remote_config import read_remote
from .parquet_remote import ParquetRemote,literal
from .bigquery_remote import BigQueryRemote
from ..engine.schema import COLUMNS,REQUIRED


def adapter(client: Any, start: str, end: str) -> Any:
    source = read_remote(client)
    if source is None:
        raise ValueError('No hay fuente remota configurada.')
    try:
        remote = (BigQueryRemote if source.kind=='bigquery' else ParquetRemote)(client,source,start,end)
    except Exception as exc:
        from .execution import SourceError
        raise SourceError(exc) from None
    from ..config import atomic_write_text
    atomic_write_text(client.workspace/'remote-schema.json',json.dumps(dict(columns=remote.columns,revision=remote.revision)))
    return remote


def normalized_relation(remote: Any, client_id: str) -> str:
    columns = {str(name).lower():str(name) for name in remote.columns}
    missing = [name for name in REQUIRED if name.lower() not in columns]
    if missing:
        raise ValueError('Faltan columnas FOCUS requeridas: '+', '.join(sorted(missing)))
    fields = [literal(client_id)+' AS client_id']
    for name,kind in COLUMNS.items():
        actual = columns.get(name.lower())
        value = '"'+actual.replace('"','""')+'"' if actual else 'NULL'
        fields.append(f'CAST({value} AS {kind}) AS "{name}"')
    return 'SELECT '+','.join(fields)+' FROM '+remote.relation


def execute_remote(remote: Any, client_id: str, sql: str, params: dict[str,Any]) -> list[dict[str,Any]]:
    tree = sqlglot.parse_one(sql,read='duckdb')
    relation = sqlglot.parse_one(normalized_relation(remote,client_id),read='duckdb')
    for table in list(tree.find_all(exp.Table)):
        if table.name.lower()=='focus_usage':
            table.replace(exp.Subquery(this=relation.copy(),alias=exp.TableAlias(this=exp.to_identifier(table.alias_or_name))))
    return list(remote.execute(tree.sql(dialect='duckdb'),params))
