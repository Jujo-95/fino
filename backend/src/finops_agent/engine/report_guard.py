"""One confirmation shared by chat and HTTP for same-day, same-period reports."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any
from ..engine.incremental_inputs import digest
from .run_audit import RunAuditStore

MESSAGE = 'Ya existe un reporte para el periodo actual, ¿desea crear uno nuevamente?'


def today() -> str:
    return datetime.now(ZoneInfo('America/Bogota')).date().isoformat()


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def repeat_prompt(client: Any, start: str, end: str) -> dict[str,Any] | None:
    matches = [r for r in RunAuditStore(client.workspace).list(None) if r['status']=='completed' and not r.get('analysis_only')
        and r['client_id']==client.profile.client_id and instant(r['period_start_utc'])==instant(start)
        and instant(r['period_end_utc'])==instant(end)
        and datetime.fromisoformat((r.get('finished_at_utc') or r['created_at_utc']).replace('Z','+00:00'))
            .astimezone(ZoneInfo('America/Bogota')).date().isoformat()==today()]
    if not matches:
        return None
    token = digest([client.profile.client_id,today(),start,end,sorted(r['run_id'] for r in matches)])
    return dict(kind='repeat_report',code='report_exists',message=MESSAGE,confirmation_id=token,
        existing_run_id=matches[0]['run_id'],period_start_utc=start,period_end_utc=end)


class ReportConfirmationRequired(ValueError):
    def __init__(self, detail: dict[str,Any]) -> None:
        super().__init__(MESSAGE)
        self.detail = detail


def require_confirmation(client: Any, body: Any) -> None:
    prompt = repeat_prompt(client,body.period_start_utc,body.period_end_utc)
    if prompt and body.repeat_confirmation!=prompt['confirmation_id']:
        raise ReportConfirmationRequired(prompt)
