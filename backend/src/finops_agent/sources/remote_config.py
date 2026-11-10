"""Tenant-scoped remote source settings. Credentials never enter these documents."""
import json
from datetime import date
from typing import Any,Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel,ConfigDict,Field,model_validator
from ..config import atomic_write_text


class RemoteSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['s3','gcs','azure','bigquery']
    bucket: str = Field(default='',pattern=r'^[a-zA-Z0-9._-]{0,220}$')
    prefix: str = Field(default='',max_length=500)
    region: str = Field(default='us-east-1',pattern=r'^[a-zA-Z0-9-]{1,50}$')
    account: str = Field(default='',pattern=r'^[a-z0-9]{0,24}$')
    project: str = Field(default='',pattern=r'^[a-z0-9-]{0,100}$')
    table: str = Field(default='',pattern=r'^[a-zA-Z0-9_.-]{0,300}$')
    location: str = Field(default='US',pattern=r'^[a-zA-Z0-9-]{1,50}$')
    focus_version: Literal['unknown','1.0','1.1','1.2','1.3','1.4'] = 'unknown'
    available_start: date
    available_end: date
    max_source_bytes: int = Field(default=1_073_741_824,ge=1048576,le=1099511627776)
    max_result_rows: int = Field(default=10000,ge=100,le=50000)
    timeout_seconds: int = Field(default=60,ge=5,le=300)
    cache_minutes: int = Field(default=60,ge=1,le=1440)
    verified_at: str | None = None

    @model_validator(mode='after')
    def valid(self) -> 'RemoteSource':
        if self.available_end<=self.available_start:
            raise ValueError('El final disponible es exclusivo y debe ser posterior al inicio.')
        if any(c in self.prefix for c in "*?[]'\\") or '..' in self.prefix or self.prefix.startswith('/'):
            raise ValueError('Usa un prefijo literal autorizado sin comodines.')
        if self.kind=='bigquery' and (len(self.table.split('.'))!=3 or not self.project):
            raise ValueError('Indica proyecto de ejecución y tabla proyecto.dataset.tabla.')
        if self.kind!='bigquery' and (not self.bucket or self.kind=='azure' and not self.account):
            raise ValueError('Indica bucket/contenedor y cuenta de Azure cuando corresponda.')
        return self


def read_remote(client: Any) -> RemoteSource | None:
    path = client.workspace/'remote-source.json'
    return RemoteSource.model_validate_json(path.read_text()) if path.exists() else None


def save_remote(client: Any, source: RemoteSource) -> None:
    atomic_write_text(client.workspace/'remote-source.json',source.model_dump_json())


class AnalysisSchedule(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    hour: int = Field(default=6,ge=0,le=23)
    minute: int = Field(default=0,ge=0,le=59)
    timezone: str = 'America/Bogota'
    latency_days: int = Field(default=2,ge=0,le=30)
    use_llm: bool = False
    create_tasks: bool = True

    @model_validator(mode='after')
    def zone(self) -> 'AnalysisSchedule':
        try:
            ZoneInfo(self.timezone)
        except (KeyError,ValueError):
            raise ValueError('Zona horaria IANA inválida.') from None
        return self


def schedule(client: Any) -> AnalysisSchedule:
    path = client.workspace/'analysis-schedule.json'
    return AnalysisSchedule.model_validate(json.loads(path.read_text())) if path.exists() else AnalysisSchedule()
