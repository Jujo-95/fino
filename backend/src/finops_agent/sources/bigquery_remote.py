"""BigQuery performs the scan; only bounded results are received here."""
from datetime import datetime,timezone
from typing import Any
import sqlglot
from sqlglot import exp
from .remote_config import RemoteSource
from .remote_credentials import google_credentials
from ..engine.incremental_inputs import digest


class BigQueryRemote:
    def __init__(self, client: Any, source: RemoteSource, start: str, end: str) -> None:
        from google.cloud import bigquery
        self.source = source
        self.sdk = bigquery.Client(project=source.project,credentials=google_credentials(client,'bigquery'),location=source.location)
        table = self.sdk.get_table(source.table,timeout=source.timeout_seconds)
        self.columns = [field.name for field in table.schema]
        self.column_types = {field.name.lower():field.field_type for field in table.schema}
        self.revision = digest([source.model_dump(mode='json',exclude={'verified_at'}),str(table.modified),table.etag])
        self.relation = '"'+source.table+'"'
        self.job: Any = None
        self.stats: dict[str,Any] = {}

    def execute(self, sql: str, parameters: dict[str,Any]) -> list[dict[str,Any]]:
        from google.cloud import bigquery
        translated = translate(sql,self.column_types)
        tree = sqlglot.parse_one(translated,read='bigquery')
        for placeholder in tree.find_all(exp.Placeholder):
            placeholder.replace(exp.Parameter(this=exp.Var(this=str(placeholder.this))))
        translated = tree.sql(dialect='bigquery')
        bound = [parameter(key,value) for key,value in parameters.items()]
        config = bigquery.QueryJobConfig(query_parameters=bound,maximum_bytes_billed=self.source.max_source_bytes,
            labels={'application':'finops-agent'},job_timeout_ms=self.source.timeout_seconds*1000)
        estimate = self.sdk.query(translated,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,query_parameters=bound),timeout=self.source.timeout_seconds)
        if (estimate.total_bytes_processed or 0)>self.source.max_source_bytes:
            raise ValueError('La consulta supera el límite de bytes autorizado.')
        self.job = self.sdk.query(translated,job_config=config,timeout=self.source.timeout_seconds)
        try:
            iterator = self.job.result(timeout=self.source.timeout_seconds,max_results=self.source.max_result_rows+1)
            rows = [dict(row.items()) for row in iterator]
            if len(rows)>self.source.max_result_rows:
                raise ValueError('Resultado demasiado grande; agrupa o reduce el alcance.')
            self.stats = dict(job_id=self.job.job_id,bytes_processed=self.job.total_bytes_processed,cache_hit=self.job.cache_hit)
            return rows
        except BaseException:
            self.job.cancel()
            raise

    def close(self) -> None:
        self.sdk.close()


def translate(sql: str, types: dict[str,str]) -> str:
    tree = sqlglot.parse_one(sql,read='duckdb')
    for cast in list(tree.find_all(exp.Cast)):
        target = cast.args.get('to')
        if target and target.this in (exp.DataType.Type.TIMESTAMP,exp.DataType.Type.TIMESTAMPNTZ):
            cast.set('to',exp.DataType.build('TIMESTAMPTZ'))
        if target and target.this==exp.DataType.Type.JSON and isinstance(cast.this,exp.Column):
            kind = types.get(cast.this.name.lower())
            if kind=='STRING':
                cast.replace(exp.ParseJSON(this=cast.this,safe=True))
            elif kind=='JSON':
                cast.replace(cast.this)
            elif kind is not None:
                raise ValueError('Tags debe ser JSON o texto JSON; esta estructura requiere una vista FOCUS del cliente.')
    for function in tree.find_all(exp.JSONExtractScalar):
        path = function.expression
        if isinstance(path,exp.Literal) and str(path.this).startswith('/'):
            import json
            function.set('expression',exp.Literal.string('$'+''.join('.'+json.dumps(p) for p in str(path.this)[1:].split('/'))))
    return str(tree.sql(dialect='bigquery',unsupported_level=sqlglot.ErrorLevel.RAISE))


def parameter(name: str, value: Any) -> Any:
    from google.cloud import bigquery
    if isinstance(value,list):
        return bigquery.ArrayQueryParameter(name,'STRING',value)
    kind = 'BOOL' if isinstance(value,bool) else 'INT64' if isinstance(value,int) else 'FLOAT64' if isinstance(value,float) else 'STRING'
    if name in ('_scope_start','_scope_end','start_utc','end_utc'):
        kind,value = 'TIMESTAMP',datetime.fromisoformat(str(value).replace('Z','+00:00')).replace(tzinfo=timezone.utc)
    return bigquery.ScalarQueryParameter(name,kind,value)
