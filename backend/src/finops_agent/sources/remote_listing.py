"""Bounded, metadata-only discovery. Signed download URLs never leave the backend."""
import re
from datetime import date
from typing import Any
from .remote_config import RemoteSource
from .remote_credentials import secret,google_credentials
from ..engine.incremental_inputs import digest


def object_day(key: str) -> str | None:
    found = re.search(r'(?:year=)?(20\d{2})[/_-](?:month=)?(\d{2})[/_-](?:day=)?(\d{2})',key)
    try:
        return date(*map(int,found.groups())).isoformat() if found else None
    except ValueError:
        return None


def objects(client: Any, source: RemoteSource, start: str | None = None, end: str | None = None) -> list[dict[str,Any]]:
    rows = []
    for index,item in enumerate(list_objects(client,source)):
        if index>=10000:
            raise ValueError('El prefijo contiene más de 10.000 objetos; reduce el alcance.')
        if not item['name'].endswith('.parquet') or not item['name'].startswith(source.prefix):
            continue
        day = object_day(item['name'])
        if day and (start and day<start[:10] or end and day>=end[:10]):
            continue
        rows.append({**item,'day':day})
    return sorted(rows,key=lambda r:r['name'])


def list_objects(client: Any, source: RemoteSource) -> Any:
    values = secret(client,source.kind)
    if source.kind=='s3':
        import boto3  # type: ignore[import-untyped]
        sdk = boto3.client('s3',region_name=source.region,**({
            'aws_access_key_id':values['access_key'],'aws_secret_access_key':values['secret_key'],
            'aws_session_token':values.get('session_token')} if values.get('access_key') else {}))
        for page in sdk.get_paginator('list_objects_v2').paginate(Bucket=source.bucket,Prefix=source.prefix):
            for obj in page.get('Contents',[]):
                yield dict(name=obj['Key'],size=obj['Size'],version=obj['ETag'],updated_at=obj['LastModified'].isoformat())
    elif source.kind=='gcs':
        from google.cloud import storage  # type: ignore[attr-defined]
        sdk = storage.Client(project=source.project or None,credentials=google_credentials(client,'gcs'))
        for obj in sdk.list_blobs(source.bucket,prefix=source.prefix):
            yield dict(name=obj.name,size=obj.size,version=str(obj.generation),updated_at=obj.updated.isoformat())
    else:
        from azure.storage.blob import BlobServiceClient
        from azure.identity import DefaultAzureCredential
        sdk = BlobServiceClient(account_url=f'https://{source.account}.blob.core.windows.net',
            credential=values.get('sas_token') or DefaultAzureCredential())
        for obj in sdk.get_container_client(source.bucket).list_blobs(name_starts_with=source.prefix):
            yield dict(name=obj.name,size=obj.size,version=str(obj.etag),updated_at=obj.last_modified.isoformat())


def source_revision(source: RemoteSource, rows: list[dict[str,Any]]) -> str:
    return digest([source.model_dump(mode='json',exclude={'verified_at'}),[(r['name'],r['version'],r['size']) for r in rows]])
