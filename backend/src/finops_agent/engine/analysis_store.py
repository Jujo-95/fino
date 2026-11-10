"""Structured analysis is the durable product; narrative reports are optional views."""
import json
from datetime import datetime,timezone
from typing import Any
from ..config import atomic_write_text


def latest_analysis(client: Any) -> dict[str,Any] | None:
    path = client.workspace/'analysis/latest.json'
    if not path.exists():
        return None
    value: dict[str,Any] = json.loads(path.read_text())
    if value['client_id']!=client.profile.client_id:
        raise ValueError('El análisis no pertenece al cliente activo.')
    return value


def save_analysis(client: Any, value: dict[str,Any]) -> None:
    from .analysis_contract import AnalysisRun
    AnalysisRun.model_validate(value)
    text = json.dumps(value,default=str,ensure_ascii=False)
    atomic_write_text(client.workspace/'analysis'/(value['run_id']+'.json'),text)
    atomic_write_text(client.workspace/'analysis/latest.json',text)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
