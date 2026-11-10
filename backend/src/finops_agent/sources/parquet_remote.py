"""Scoped, ephemeral DuckDB reader. No raw rows are inserted into client storage."""
import threading
from typing import Any
from urllib.parse import quote
import duckdb
from .remote_config import RemoteSource
from .remote_credentials import secret,google_credentials
from .remote_listing import objects,source_revision
from .extensions import load


def literal(value: str) -> str:
    return "'"+value.replace("'","''")+"'"


class ParquetRemote:
    def __init__(self, client: Any, source: RemoteSource, start: str, end: str) -> None:
        self.source = source
        self.rows = objects(client,source,start,end)
        if not self.rows:
            raise ValueError('No hay archivos Parquet disponibles para este alcance.')
        if sum(row['size'] for row in self.rows)>source.max_source_bytes:
            raise ValueError('El tamaño de los archivos seleccionados supera el límite. Reduce el período o usa un motor en la nube del cliente.')
        self.revision = source_revision(source,self.rows)
        self.stats = dict(selected_file_bytes=sum(r['size'] for r in self.rows),transferred_bytes=None)
        self.conn = duckdb.connect(':memory:')
        self.conn.execute("SET memory_limit='512MB'")
        self.conn.execute("SET temp_directory=''")
        try:
            uris = authenticate(self.conn,client,source,self.rows)
            self.relation = 'read_parquet(['+','.join(literal(u) for u in uris)+'], union_by_name=false)'
            self.columns = [r[0] for r in self.conn.execute('DESCRIBE SELECT * FROM '+self.relation).fetchall()]
        except BaseException:
            self.conn.close()
            raise

    def execute(self, sql: str, parameters: dict[str,Any]) -> list[dict[str,Any]]:
        timer = threading.Timer(self.source.timeout_seconds,self.conn.interrupt)
        timer.start()
        try:
            cursor = self.conn.execute(sql,parameters)
            names = [r[0] for r in cursor.description]
            rows = cursor.fetchmany(self.source.max_result_rows+1)
            if len(rows)>self.source.max_result_rows:
                raise ValueError('Resultado demasiado grande; agrupa o reduce el alcance.')
            return [dict(zip(names,row)) for row in rows]
        finally:
            timer.cancel()
            timer.join()

    def close(self) -> None:
        self.conn.close()


def authenticate(conn: Any, client: Any, source: RemoteSource, rows: list[dict[str,Any]]) -> list[str]:
    values = secret(client,source.kind)
    if source.kind=='s3':
        load(conn,'httpfs',client)
        fields = dict(TYPE='s3',REGION=source.region,SCOPE=f's3://{source.bucket}/{source.prefix}')
        if values.get('access_key'):
            fields.update(KEY_ID=values['access_key'],SECRET=values['secret_key'])
            if values.get('session_token'):
                fields['SESSION_TOKEN'] = values['session_token']
        else:
            fields['PROVIDER'] = 'credential_chain'
        conn.execute('CREATE SECRET remote_source ('+', '.join(k+' '+literal(v) for k,v in fields.items())+')')
        return [f"s3://{source.bucket}/{r['name']}" for r in rows]
    if source.kind=='azure':
        load(conn,'azure',client)
        fields = dict(TYPE='azure',ACCOUNT_NAME=source.account,SCOPE=f'az://{source.account}.blob.core.windows.net/{source.bucket}/{source.prefix}')
        if not values.get('sas_token'):
            fields['PROVIDER'] = 'credential_chain'
            conn.execute('CREATE SECRET remote_source ('+', '.join(k+' '+literal(v) for k,v in fields.items())+')')
            return [f"az://{source.account}.blob.core.windows.net/{source.bucket}/{r['name']}" for r in rows]
        load(conn,'httpfs',client)
        return [f"https://{source.account}.blob.core.windows.net/{source.bucket}/{quote(r['name'],safe='/')}?{values['sas_token'].lstrip('?')}" for r in rows]
    return gcs_uris(conn,client,source,rows)


def gcs_uris(conn: Any, client: Any, source: RemoteSource, rows: list[dict[str,Any]]) -> list[str]:
    import google.auth
    from google.auth.transport.requests import Request
    credentials = google_credentials(client,'gcs') or google.auth.default(scopes=['https://www.googleapis.com/auth/devstorage.read_only'])[0]
    credentials.refresh(Request())
    load(conn,'httpfs',client)
    scope = f'https://storage.googleapis.com/{source.bucket}/'
    conn.execute('CREATE SECRET remote_source (TYPE http, SCOPE '+literal(scope)+', BEARER_TOKEN '+literal(credentials.token)+')')
    return [scope+quote(r['name'],safe='/')+'?generation='+quote(r['version'],safe='') for r in rows]
