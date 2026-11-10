import calendar
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any
from ..models import ClientProfile
from .duckdb_engine import DuckDBFocusEngine
from .context import recalled_suppressions
from .kpi_catalog import metrics
from .query_audit import query_with_evidence


def ratio(a: float, b: float | None) -> float | None:
    return a / b * 100 if b else None


def analyze(engine: DuckDBFocusEngine, profile: ClientProfile, start: str, end: str,
            suppressed: set[str] | None = None, memory: Any = None, capture: bool = False) -> dict[str, Any]:
    params = dict(client_id=profile.client_id, start_utc=start, end_utc=end, currency=profile.billing_currency)
    evidence: list[dict[str, Any]] = []
    totals = query_with_evidence(engine, "totals", {**params,
        "required_tags": profile.allocation_policy.required_tags,
        "shared_accounts": profile.allocation_policy.shared_cost_sub_accounts}, evidence)[0]
    daily = query_with_evidence(engine, "daily", params, evidence)
    services = query_with_evidence(engine, "services", params, evidence)
    spikes = detect_spikes(services)
    context_evidence: list[dict[str, Any]] = []
    recalled = recalled_suppressions(memory, profile.client_id, [s["key"] for s in spikes], start, end,
                                    context_evidence if capture else None) if memory else set()
    overview = summarize(profile, totals, daily, services, spikes, (suppressed or set()) | recalled, start, end)
    if capture:
        overview["query_evidence"] = evidence
        overview["context_evidence"] = context_evidence
    return overview


def detect_spikes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["account"] + ":" + row["service"]].append(row)
    results = []
    for key, history in groups.items():
        if len(history) < 4:
            continue
        base = [float(row["cost"]) for row in history[:-1]]
        mean, deviation = statistics.mean(base), statistics.pstdev(base)
        latest = history[-1]
        variance = float(latest["cost"]) - mean
        if variance > max(3 * deviation, abs(mean) * 0.3, 10):
            results.append({**latest, "key": key, "baseline": mean, "variance": variance})
    return results


def summarize(profile: ClientProfile, totals: dict[str, Any], daily: list[dict[str, Any]],
              services: list[dict[str, Any]], spikes: list[dict[str, Any]], suppressed: set[str],
              start: str, end: str) -> dict[str, Any]:
    cutoff = date.fromisoformat(end[:10])
    start_day = date.fromisoformat(start[:10])
    elapsed = max(1, (cutoff - start_day).days)
    days = calendar.monthrange(start_day.year, start_day.month)[1]
    remaining = max(0, days - elapsed)
    actual = float(totals["actual"])
    variance = sum(row["variance"] for row in spikes)
    forecast = actual + max(0, (actual - variance) / elapsed) * remaining + profile.planned_monthly_cost
    active = [row for row in spikes if row["key"] not in suppressed]
    values = compute_values(profile, totals, active, forecast, elapsed, remaining)
    services_total: dict[str, float] = defaultdict(float)
    for row in services:
        services_total[row["service"]] += row["cost"]
    return dict(actual=actual, forecast=forecast, quarterly_forecast=forecast * 3,
                budget=profile.budget_policy.total_monthly_budget_usd, metrics=metrics(values),
                daily=[{**row, "day": str(row["day"])} for row in daily],
                services=[{"name": name, "cost": cost} for name, cost in services_total.items()],
                spikes=[{**row, "day": str(row["day"])} for row in active],
                excluded_baseload=[row["key"] for row in spikes],
                clean_baseload=clean_baseload(services, {row["key"] for row in spikes}),
                period_start_utc=start, period_end_utc=end, billing_currency=profile.billing_currency,
                profile=profile.model_dump(), observed_days=totals["observed_days"], generated_at_utc=datetime.now(timezone.utc).isoformat())


def compute_values(profile: ClientProfile, t: dict[str, Any], active: list[dict[str, Any]],
                   forecast: float, elapsed: int, remaining: int) -> dict[str, float | None]:
    variance = sum(row["variance"] for row in active)
    ai_spikes = sum(row["variance"] for row in active if row["category"].lower() in
                    ("ai", "machine learning", "ai and machine learning"))
    used, total = float(t["used_commitment"] or 0), float(t["commitment"] or 0)
    return {
        "unallocated_cost_pct": ratio(t["unallocated"] or 0, t["actual"]),
        "allocation_accuracy_index": ratio(t["direct"] or 0, t["actual"]),
        "shared_cost_apportionment": None,  # Requires posted apportionment records, not inferred allocations.
        "anomaly_unpredicted_variance": variance, "anomaly_cost_avoidance": variance * remaining,
        "genai_anomaly_detection_rate": ratio(ai_spikes, t["ai_total"]),
        "forecast_accuracy_usage": ratio((profile.forecasted_usage_quantity or 0) - (t["usage"] or 0),
                                         profile.forecasted_usage_quantity),
        "forecast_drift_rate": ratio(forecast - (profile.previous_forecast_spend or 0), profile.previous_forecast_spend),
        "budget_burn_rate": t["actual"] / elapsed,
        "budget_vs_forecast_variance": ratio(profile.budget_policy.total_monthly_budget_usd - forecast,
                                              profile.budget_policy.total_monthly_budget_usd),
        "commitment_utilization_score": ratio(used, total),
        "commitment_discount_waste_pct": ratio(total - used, total),
        "effective_savings_rate": (100 - (ratio(t["actual"], t["equivalent"]) or 0)) if t["equivalent"] else None,
    }


def clean_baseload(rows: list[dict[str, Any]], excluded: set[str]) -> float:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row["account"] + ":" + row["service"] not in excluded:
            groups[row["account"] + ":" + row["service"]].append(float(row["on_demand"]))
    return sum(min(values) for values in groups.values() if len(values) >= 4)
