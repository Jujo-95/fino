import json
from datetime import date
from typing import Any
from pydantic import BaseModel
from .routes import router, Container
from ..sources.models import load_source
from ..sources.s3 import sync


class SourceSyncRequest(BaseModel):
    through: date | None = None


@router.get('/clients/{client_id}/source')
def source_status(client_id: str, c: Container) -> dict[str, Any]:
    client = c.client(client_id)
    if not (client.workspace/'source.json').exists():
        return dict(configured=False,kind='local_csv')
    source,_ = load_source(client.workspace)
    status = client.workspace/'source-status.json'
    from ..config import ROOT
    published = ROOT/'.lab'/client_id/'published.json'
    lab = json.loads(published.read_text()) if source.synthetic and published.exists() else None
    if lab:
        lab['total_days'] = json.loads((published.parent/'manifest.json').read_text())['days']
    return dict(laboratory=lab,configured=True,kind='s3',bucket=source.bucket,prefix=source.prefix,synthetic=source.synthetic,
                last_sync=json.loads(status.read_text()) if status.exists() else None)


@router.post('/clients/{client_id}/source/sync')
def sync_source(client_id: str, body: SourceSyncRequest, c: Container) -> dict[str, Any]:
    client = c.client(client_id)
    if not (client.workspace/'source.json').exists():
        raise ValueError('Este cliente todavía no tiene una fuente conectada.')
    return sync(client,body.through)


class AdvanceRequest(BaseModel):
    expected_days: int


@router.post('/clients/{client_id}/source/advance')
def advance_source(client_id: str, body: AdvanceRequest, c: Container) -> dict[str, Any]:
    from ..config import ROOT
    from ..lab.advance import advance
    return advance(c.client(client_id),ROOT/'.lab',body.expected_days)
