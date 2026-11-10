"""Unchanged sources reuse retained measurements beyond disposable-cache expiry."""
import calendar
from datetime import date
from typing import Any
from ..engine.analysis_store import latest_analysis
from ..engine.analytics import compute_values
from ..engine.kpi_catalog import metrics


def reuse(client: Any, remote: Any, profile: Any, start: str, end: str, confirmed: bool) -> dict[str,Any] | None:
    previous = latest_analysis(client)
    if not previous or previous['query_catalog_version']!='base-aggregates-v1':
        return None
    old = previous['overview']
    if not old.get('measurement_basis') or previous['period']!=dict(start=start,end=end):
        return None
    if old['profile']['allocation_policy']!=profile.allocation_policy.model_dump():
        return None
    if any(q.get('source_revision')!=remote.revision for q in old.get('query_evidence',[])):
        return None
    totals = old['measurement_basis']
    elapsed = max(1,(date.fromisoformat(end[:10])-date.fromisoformat(start[:10])).days)
    month_days = calendar.monthrange(int(start[:4]),int(start[5:7]))[1]
    remaining = max(0,month_days-elapsed)
    variance = sum(row['variance'] for row in old['spikes'])
    forecast = float(totals['actual'])+max(0,(float(totals['actual'])-variance)/elapsed)*remaining+profile.planned_monthly_cost
    return dict(old,profile=profile.model_dump(),budget=profile.budget_policy.total_monthly_budget_usd,
        budget_confirmed=confirmed,forecast=forecast,quarterly_forecast=forecast*3,
        metrics=metrics(compute_values(profile,totals,old['spikes'],forecast,elapsed,remaining)),
        query_evidence=[dict(q,cache_hit=True,reused_retained_measurement=True) for q in old['query_evidence']])
