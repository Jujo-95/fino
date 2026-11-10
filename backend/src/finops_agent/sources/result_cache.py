"""Bounded aggregate cache; source revisions and tenant are part of every key."""
import hashlib
import json
import os
from io import StringIO
from datetime import datetime, timezone, timedelta
from typing import Any
from ..config import atomic_write_text
from .remote_query import adapter
from .execution import execute,SourceError


def remote_result(client: Any, sql: str, params: dict[str,Any], start: str, end: str, connection: Any = None) -> dict[str,Any]:
    try:
        remote = connection or adapter(client,start,end)
    except Exception as exc:
        raise SourceError(exc) from None
    client.query_lock.acquire()
    try:
        identity = dict(client=client.profile.client_id,revision=remote.revision,sql=sql,parameters=params,version=1)
        key = hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
        path = client.workspace/'query_cache'/(key+'.json')
        now = datetime.now(timezone.utc)
        if path.exists():
            cached = json.loads(path.read_text())
            if datetime.fromisoformat(cached['expires_at'])>now:
                return dict(cached,rows=read_rows(path,cached),cache_hit=True)
        rows = execute(remote,client.profile.client_id,sql,params)
        result = dict(**identity,rows=rows,row_count=len(rows),complete=True,cache_hit=False,
            created_at=now.isoformat(),expires_at=(now+timedelta(minutes=remote.source.cache_minutes)).isoformat(),
            execution=getattr(remote,'stats',{}))
        persist(client,path,key,result)
        return result
    except InterruptedError:
        raise
    except Exception as exc:
        raise SourceError(exc) from None
    finally:
        client.query_lock.release()
        if connection is None:
            remote.close()


def read_rows(path: Any, cached: dict[str,Any]) -> list[dict[str,Any]]:
    if cached.get('result_format')!='parquet':
        return list(cached['rows'])
    import duckdb
    with duckdb.connect(':memory:') as conn:
        cursor = conn.execute('SELECT * FROM read_parquet(?)',[str(path.with_suffix('.parquet'))])
        names = [item[0] for item in cursor.description]
        return [dict(zip(names,row)) for row in cursor.fetchall()]


def persist(client: Any, path: Any, key: str, result: dict[str,Any]) -> None:
    if len(json.dumps(result,default=str).encode())>16*1024*1024:
        raise ValueError('Resultado superior a 16 MiB; agrega o reduce la consulta.')
    payload = dict(result,result_format='json')
    path.parent.mkdir(parents=True,exist_ok=True)
    if len(result['rows'])>500:
        import duckdb
        temporary = path.with_suffix('.parquet.tmp')
        with duckdb.connect(':memory:') as conn:
            relation = conn.read_json(StringIO(json.dumps(result['rows'],default=str)))
            relation.write_parquet(str(temporary))
        os.replace(temporary,path.with_suffix('.parquet'))
        payload.pop('rows')
        payload['result_format'] = 'parquet'
    atomic_write_text(path,json.dumps(payload,default=str))
    with client.engine.lock:
        client.engine.conn.execute('CREATE TABLE IF NOT EXISTS query_results (cache_key VARCHAR PRIMARY KEY,metadata JSON,result_path VARCHAR,expires_at TIMESTAMP)')
        metadata = {k:v for k,v in payload.items() if k!='rows'}
        client.engine.conn.execute('INSERT OR REPLACE INTO query_results VALUES (?,?,?,?)',
            [key,json.dumps(metadata,default=str),str(path),result['expires_at']])
        prune(client,path.parent)


def prune(client: Any, directory: Any) -> None:
    from pathlib import Path
    records = client.engine.conn.execute('SELECT cache_key,result_path,expires_at<current_timestamp FROM query_results ORDER BY expires_at DESC').fetchall()
    retained = 0
    for index,(key,name,expired) in enumerate(records):
        path = Path(name)
        if path.parent!=directory:
            continue
        paths = (path,path.with_suffix('.parquet'))
        size = sum(p.stat().st_size for p in paths if p.exists())
        if expired or index>=200 or retained+size>128*1024*1024:
            for item in paths:
                item.unlink(missing_ok=True)
            client.engine.conn.execute('DELETE FROM query_results WHERE cache_key=?',[key])
        else:
            retained += size
