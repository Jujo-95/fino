"""A measured budget overrun can outrank the objective; severity alone cannot."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any
from .store import ConsultingStore
from ..engine.analysis_store import latest_analysis


def budget_risk(analysis: dict[str,Any] | None, context: dict[str,Any], profile: Any, today: date) -> dict[str,Any] | None:
    if not analysis or analysis.get('status') not in ('completed','partial','skipped'):
        return None
    values = context['values']
    if analysis.get('context_revision')!=context['revision'] or values.get('monthly_budget') is None:
        return None
    latency,cadence = values.get('data_latency_days'),values.get('source_cadence_days')
    overview = analysis.get('overview',{})
    days = [date.fromisoformat(str(r['day'])[:10]) for r in overview.get('daily',[]) if r.get('day')]
    if latency is None or cadence is None or not days or not 0<=(today-max(days)).days<=latency+cadence:
        return None
    if analysis.get('period',{}).get('start','')[:10]!=today.replace(day=1).isoformat():
        return None
    if any(d.year!=today.year or d.month!=today.month or d>today for d in days):
        return None
    if profile.billing_currency!='USD' or overview.get('billing_currency')!='USD':
        return None
    evidence = [q['query_id'] for q in analysis.get('evidence',[]) if q.get('query_id') and q.get('status')=='completed']
    tolerance = dict(Crawl=20,Walk=15,Run=12)[profile.target_maturity]
    budget,actual = values['monthly_budget'],overview.get('actual')
    if not evidence or actual is None or actual<=budget*(1+tolerance/100):
        return None
    return dict(run_id=analysis['run_id'],evidence_refs=evidence,threshold=budget*(1+tolerance/100),
        reason=f'El gasto observado ({actual:,.2f} USD) supera el presupuesto confirmado ({budget:,.2f} USD) y su umbral de variación ({tolerance}%).')


def urgent_budget(client: Any) -> dict[str,Any] | None:
    today = datetime.now(timezone.utc).astimezone(ZoneInfo('America/Bogota')).date()
    return budget_risk(latest_analysis(client),ConsultingStore(client).context(),client.profile,today)
