"""Default, explicit verification plans for optimization findings."""
from datetime import date
from typing import Any, Literal
from .followup_models import FollowupPlan


def event_date(period: str) -> date:
    value = period.replace('/', ':').split(':')[0].strip()[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


def default_plan(finding: Any) -> FollowupPlan | None:
    if finding.ticket_kind != 'finding':
        return None
    current = min(event_date(finding.period_bucket), date.today())
    check: Literal['return_to_baseline', 'specialist_review'] = (
        'return_to_baseline' if finding.capability == 'anomaly-management' else 'specialist_review')
    criterion = finding.action_details.completion_criterion or (
        'Comparar el período posterior con la línea base y confirmar el resultado con evidencia.'
    )
    return FollowupPlan(reason='Verificar el resultado de la acción propuesta.', event_date=current,
        observation_days=3, baseline_days=7, check=check, tolerance_pct=20,
        closure_criterion=criterion)
