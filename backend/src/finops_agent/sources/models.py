import json
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, SecretStr, model_validator
from ..config import atomic_write_text


class S3Source(BaseModel):
    client_id: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{0,63}$')
    endpoint: str
    bucket: str = Field(pattern=r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$')
    prefix: str = 'focus/'
    region: str = 'us-east-1'
    synthetic: bool = False

    @model_validator(mode='after')
    def valid_endpoint(self) -> 'S3Source':
        u = urlsplit(self.endpoint)
        if u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise ValueError('S3 endpoint must be an origin without credentials or path')
        if not u.hostname or (u.scheme!='https' and not (u.scheme=='http' and u.hostname in ('localhost','127.0.0.1'))):
            raise ValueError('Use HTTPS or a loopback HTTP laboratory endpoint')
        if not self.prefix.endswith('/') or any(c in self.prefix for c in "*?[]'\\") or '..' in self.prefix:
            raise ValueError('Use a literal partition prefix ending in /')
        if not self.region.replace('-','').isalnum():
            raise ValueError('Invalid region')
        return self


class S3Credentials(BaseModel):
    access_key: SecretStr
    secret_key: SecretStr


def load_source(workspace: Path) -> tuple[S3Source, S3Credentials]:
    source = S3Source.model_validate_json((workspace/'source.json').read_text())
    if source.client_id!=workspace.name:
        raise ValueError('Source belongs to another client')
    credentials = S3Credentials.model_validate_json((workspace/'storage/s3-credentials.json').read_text())
    return source,credentials


def save_source(workspace: Path, source: S3Source, key: dict[str, str]) -> None:
    if source.client_id!=workspace.name:
        raise ValueError('Source belongs to another client')
    target = workspace/'storage/s3-credentials.json'
    atomic_write_text(target,json.dumps(dict(access_key=key['AccessKeyId'],secret_key=key['SecretAccessKey'])))
    target.chmod(0o600)
    atomic_write_text(workspace/'source.json',source.model_dump_json(indent=2))
