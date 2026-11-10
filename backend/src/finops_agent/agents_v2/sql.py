"""Read-only SQL on a server-injected client/date/currency relation; no external IO."""
import threading
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4
import sqlglot
from sqlglot import exp
from ..engine.schema import COLUMNS


def parse_query(sql: str) -> exp.Expression:
    if not 1 <= len(sql) <= 24000:
        raise ValueError('La consulta excede el límite permitido.')
    statements = sqlglot.parse(sql,read='duckdb')
    if len(statements)!=1 or not isinstance(statements[0],(exp.Select,exp.Union)):
        raise ValueError('Solo se permite una consulta SELECT de lectura.')
    tree = statements[0]
    if tree.find(exp.Into) or tree.find(exp.Lock):
        raise ValueError('La consulta no puede escribir ni bloquear datos.')
    if len(list(tree.walk()))>3000:
        raise ValueError('Consulta demasiado compleja.')
    for func in tree.find_all(exp.Func):
        if isinstance(func,exp.Anonymous) or any(word in func.sql_name().lower() for word in ('read_','scan','pragma','query','write','http','glob','attach','getenv','extension')):
            raise ValueError('Funciones externas o no autorizadas.')
    return tree


def scoped_query(sql: str) -> exp.Expression:
    tree = parse_query(sql)
    ctes = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
    if ctes & {'focus_data_table','focus_usage'}:
        raise ValueError('No se permite redefinir la fuente de datos.')
    tables = list(tree.find_all(exp.Table))
    physical = 0
    for table in tables:
        if not isinstance(table.this,exp.Identifier) or table.db or table.catalog:
            raise ValueError('Solo se permite la tabla FOCUS del cliente.')
        if table.name.lower() in ctes:
            continue
        if table.name.lower() not in ('focus_data_table','focus_usage'):
            raise ValueError('Solo se permite la tabla FOCUS del cliente.')
        alias = table.alias_or_name
        relation = sqlglot.parse_one('SELECT '+','.join(COLUMNS)+' FROM focus_usage WHERE client_id=$_scope_client '
            'AND ChargePeriodStart >= $_scope_start AND ChargePeriodStart < $_scope_end AND BillingCurrency=$_scope_currency',read='duckdb')
        table.replace(exp.Subquery(this=relation,alias=exp.TableAlias(this=exp.to_identifier(alias))))
        physical += 1
    if not physical:
        raise ValueError('La consulta debe leer datos FOCUS autorizados.')
    limit = tree.args.get('limit')
    count = min(101,max(0,int(limit.expression.this))) if limit and isinstance(limit.expression,exp.Literal) and limit.expression.is_int else 101
    return cast(Any,tree).limit(count)


def validate_query_window(start: str, end: str) -> None:
    first = datetime.fromisoformat(start.replace('Z','+00:00'))
    last = datetime.fromisoformat(end.replace('Z','+00:00'))
    if any(value.utcoffset() not in (None,timedelta(0)) for value in (first,last)):
        raise ValueError('Las consultas requieren fechas UTC.')
    first,last = first.replace(tzinfo=None),last.replace(tzinfo=None)
    if not timedelta(0)<last-first<=timedelta(days=366):
        raise ValueError('La ventana de consulta debe ser positiva y de máximo 366 días.')


def query(client: Any, sql: str, start: str, end: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_query_window(start,end)
    tree = scoped_query(sql)
    params = dict(parameters or {})
    if any(key.startswith('_scope_') for key in params):
        raise ValueError('El alcance del cliente lo fija el servidor.')
    params.update(_scope_client=client.profile.client_id,_scope_start=start,_scope_end=end,_scope_currency=client.profile.billing_currency)
    wanted = {str(item.this) for item in tree.find_all(exp.Placeholder)}
    if any(not item.this for item in tree.find_all(exp.Placeholder)) or not wanted <= params.keys():
        raise ValueError('Usa parámetros con nombre y proporciona sus valores.')
    from ..sources.remote_config import read_remote
    if read_remote(client):
        from ..sources.result_cache import remote_result
        result = remote_result(client,tree.sql(dialect='duckdb'),{key:params[key] for key in wanted},start,end)
        values = result['rows']
        return dict(evidence_id='v2-query:'+uuid4().hex,client_id=client.profile.client_id,source='query',
            period_start_utc=start,period_end_utc=end,columns=list(values[0]) if values else [],rows=values[:100],
            rowCount=min(len(values),100),truncated=len(values)>100,sql=sql,executed_sql=tree.sql(dialect='duckdb'),
            source_revision=result['revision'],cache_hit=result['cache_hit'])
    with client.engine.lock:
        timer = threading.Timer(15,client.engine.conn.interrupt)
        timer.daemon = True
        timer.start()
        try:
            cursor = client.engine.conn.execute(tree.sql(dialect='duckdb'),{key:params[key] for key in wanted})
            columns = [item[0] for item in cursor.description]
            rows = cursor.fetchmany(101)
        finally:
            timer.cancel()
            timer.join()
    return dict(evidence_id='v2-query:'+uuid4().hex,client_id=client.profile.client_id,source='query',
        period_start_utc=start,period_end_utc=end,columns=columns,rows=[dict(zip(columns,row)) for row in rows[:100]],
        rowCount=min(len(rows),100),truncated=len(rows)>100,sql=sql,executed_sql=tree.sql(dialect='duckdb'))
