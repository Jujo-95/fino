from typing import Any
from ..engine.kpi_catalog import KPI_SPECS
from ..models import Finding
from ..consulting.models import ActionDetails
from .specs import SpecialistSpec


def finding(spec: SpecialistSpec, overview: dict[str, Any], key: str, value: float,
            title: str, action: str, impact: float = 0, account: str = "all", service: str = "all") -> Finding:
    profile = overview["profile"]
    return Finding(capability=spec.capability_slug, action_details=ActionDetails(action_type='improvement',
        steps=[action], completion_criterion='Confirmar el resultado en una nueva lectura con evidencia del período posterior.'),
        maturity_tier=profile["target_maturity"],
        allocation_mode=profile["allocation_policy"]["mode"] if spec.name == "Allocation" else "N/A",
        severity="HIGH" if spec.name in ("Anomaly", "Budgeting") else "MEDIUM",
        sub_account_id=account, service_name=service, period_bucket=overview["period_start_utc"][:7],
        kpi_name=key, kpi_value=value, estimated_monthly_impact_usd=max(0, impact), title=title,
        evidence_summary=f"{KPI_SPECS[key].formula} = {value:,.2f}. Currency: USD. Timezone: UTC.",
        recommended_action=action,
        capability_citation_url=f"https://www.finops.org/framework/capabilities/{spec.capability_slug}/")


def recommendations(spec: SpecialistSpec, o: dict[str, Any]) -> list[Finding]:
    values = {metric["key"]: metric["value"] for metric in o["metrics"]}
    profile = o["profile"]
    key = spec.kpi_keys[0]
    value = values.get(key)
    if spec.name == "Anomaly":
        return [finding(spec, o, key, row["variance"], f"Unexpected cost spike · {row['service']}",
                "Verify the workload and owner; stop orphaned usage or document the approved run window.",
                row["variance"] * 30, row["account"], row["service"]) for row in o["spikes"]]
    if spec.name == "Allocation" and value and value > 5:
        return [finding(spec, o, key, value, "Close the cloud ownership gap",
                "Apply the required owner, env, cost_center and service tags before allocating spend.",
                o["actual"] * value / 100)]
    if spec.name == "Forecasting" and value is not None and abs(value) > 10:
        return [finding(spec, o, key, value, "Review forecast drift",
                "Reconcile approved business drivers against the anomaly-adjusted baseline.")]
    if spec.name == "Budgeting" and value is not None:
        return budget_finding(spec, o, key, value)
    if spec.name == "Commitments" and value and value > 5:
        return [finding(spec, o, key, value, "Recover unused commitment value",
                "Reassign unused commitments; review utilization before purchasing additional coverage.")]
    if spec.name == "Commitments" and o["clean_baseload"] > 0:
        policy = profile["commitment_policy"]
        return [finding(spec, o, "effective_savings_rate", values.get("effective_savings_rate") or 0,
                "Review stable on-demand coverage",
                f"Evaluate up to {policy['max_term_months']} months of coverage for a stable daily baseload "
                f"of ${o['clean_baseload']:,.2f}. Excludes anomalous account/service pairs. "
                f"Upfront payment allowed: {policy['allow_upfront_payment']}. Validate provider quotes first.")]
    return []


def budget_finding(spec: SpecialistSpec, o: dict[str, Any], key: str, value: float) -> list[Finding]:
    profile = o["profile"]
    threshold = {"Crawl": 20, "Walk": 15, "Run": 12}[profile["target_maturity"]]
    holdback = profile["budget_policy"]["holdback_pct"]
    if value >= -threshold and o["forecast"] <= o["budget"] * (1 - holdback / 100):
        return []
    return [finding(spec, o, key, value, "Forecast is approaching the budget guardrail",
            f"Review the {holdback}% holdback and the {threshold}% maturity variance threshold. "
            "Confirm a revised budget or prioritize engineering remediation.", max(0, o["forecast"] - o["budget"]))]
