import json
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit
import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from ..config import atomic_write_text
from .models import S3Source, S3Credentials, load_source


def sdk(source: S3Source, credentials: S3Credentials) -> Any:
    return boto3.client('s3',endpoint_url=source.endpoint,region_name=source.region,
        aws_access_key_id=credentials.access_key.get_secret_value(),
        aws_secret_access_key=credentials.secret_key.get_secret_value(),
        config=Config(signature_version='s3v4',request_checksum_calculation='when_required',response_checksum_validation='when_required',s3={'addressing_style':'path'},
                      connect_timeout=5,read_timeout=30,retries={'max_attempts':2}))


def configure(conn: Any, source: S3Source, credentials: S3Credentials) -> None:
    def quote(value: str) -> str:
        return "'"+value.replace("'","''")+"'"
    origin = urlsplit(source.endpoint)
    conn.execute('LOAD httpfs')
    options = dict(KEY_ID=credentials.access_key.get_secret_value(),SECRET=credentials.secret_key.get_secret_value(),
                   REGION=source.region,ENDPOINT=origin.netloc,URL_STYLE='path',SCOPE=f's3://{source.bucket}/{source.prefix}')
    fields = ', '.join(f'{key} {quote(value)}' for key,value in options.items())
    conn.execute(f"CREATE OR REPLACE SECRET finops_source (TYPE s3, {fields}, USE_SSL {'true' if origin.scheme=='https' else 'false'})")


def partitions(client: Any, source: S3Source, through: date | None = None) -> list[dict[str, Any]]:
    result = []
    options = dict(Bucket=source.bucket) if source.synthetic else dict(Bucket=source.bucket,Prefix=source.prefix)
    for page in client.get_paginator('list_objects_v2').paginate(**options):
        for obj in page.get('Contents',[]):
            key = obj['Key']
            if not key.endswith('/usage.csv') or not key.startswith(source.prefix):
                continue
            try:
                relative = key[len(source.prefix):].replace('year=','').replace('month=','').replace('day=','')
                day = datetime.strptime(relative, '%Y/%m/%d/usage.csv').date()
            except ValueError:
                continue
            if through is None or day<=through:
                if obj.get('Size',0)>50*1024*1024:
                    raise ValueError('Partition exceeds the 50 MB CSV limit')
                result.append(dict(key=key,etag=obj['ETag'],day=day.isoformat()))
    return sorted(result,key=lambda item:item['key'])


def ingest_object(engine: Any, source: S3Source, client: Any, obj: dict[str, Any]) -> int:
    uri = f"s3://{source.bucket}/{obj['key']}"
    with engine.atomic_tx() as tx:
        tx.execute('CREATE TABLE IF NOT EXISTS source_objects (client_id VARCHAR, uri VARCHAR, etag VARCHAR, '
                   'sha256 VARCHAR, rows BIGINT, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(client_id,uri))')
        seen = tx.execute('SELECT etag,sha256 FROM source_objects WHERE client_id=? AND uri=?',[source.client_id,uri]).fetchone()
        if seen and seen[0]==obj['etag']:
            return 0
        digest = tx.execute('SELECT sha256(content) FROM read_blob(?)',[uri]).fetchone()[0]
        if seen and seen[1]!=digest:
            raise ValueError('Published daily partitions are immutable; use a new partition')
        tx.execute('CREATE OR REPLACE TEMP TABLE incoming AS SELECT * FROM read_csv_auto(?, all_varchar=true)',[uri])
        bad = tx.execute('SELECT count(*) FROM incoming WHERE TRY_CAST(ChargePeriodStart AS DATE) IS NULL OR '
                         'CAST(ChargePeriodStart AS DATE)<>CAST(? AS DATE)',[obj['day']]).fetchone()[0]
        if bad:
            raise ValueError('Rows do not belong to the daily partition')
        current = client.head_object(Bucket=source.bucket,Key=obj['key'])['ETag']
        if current!=obj['etag']:
            raise ValueError('Object changed during ingestion; retry the partition')
        rows = engine.ingest_prepared(source.client_id,digest,uri)
        tx.execute('INSERT OR REPLACE INTO source_objects(client_id,uri,etag,sha256,rows) VALUES (?,?,?,?,?)',
                   [source.client_id,uri,current,digest,rows])
        return int(rows)


def sync(client: Any, through: date | None = None) -> dict[str, Any]:
    source,credentials = load_source(client.workspace)
    remote = sdk(source,credentials)
    rows = 0
    try:
        objects = partitions(remote,source,through)
        with client.engine.lock:
            configure(client.engine.conn,source,credentials)
            try:
                for obj in objects:
                    rows += ingest_object(client.engine,source,remote,obj)
            finally:
                client.engine.conn.execute('DROP SECRET IF EXISTS finops_source')
    except Exception as error:
        raise ValueError('No se pudo sincronizar la fuente S3; revisa disponibilidad, credenciales y particiones.') from error
    result = dict(status='ready',synthetic=source.synthetic,objects=len(objects),ingested_rows=rows,
        through=objects[-1]['day'] if objects else None,synced_at=datetime.now(timezone.utc).isoformat())
    atomic_write_text(client.workspace/'source-status.json',json.dumps(result))
    return result
