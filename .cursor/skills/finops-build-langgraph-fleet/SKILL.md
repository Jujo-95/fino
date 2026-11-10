---
name: finops-build-langgraph-fleet
description: Build and extend the LangGraph Orchestrator and the 5 FinOps Specialist Agents using a single DRY SpecialistRunner and declarative SpecialistSpec. Use whenever creating or modifying LangGraph state, nodes, edges, prompts, or specialist agents.
---

# FinOps LangGraph Fleet Skill (Extend, Don't Repeat)

## Capabilities Covered
- `@finops_capabilities_md/capabilities/allocation.md` (https://www.finops.org/framework/capabilities/allocation/)
- `@finops_capabilities_md/capabilities/anomaly-management.md` (https://www.finops.org/framework/capabilities/anomaly-management/)
- `@finops_capabilities_md/capabilities/forecasting.md` (https://www.finops.org/framework/capabilities/forecasting/)
- `@finops_capabilities_md/capabilities/budgeting.md` (https://www.finops.org/framework/capabilities/budgeting/)
- `@finops_capabilities_md/capabilities/rate-optimization.md` (https://www.finops.org/framework/capabilities/rate-optimization/)

## Anti-Bloat Rule: 1 Runner Class + 5 Declarative Specs

Never write 5 separate agent classes. Define one `SpecialistSpec` dataclass and one `SpecialistRunner` callable class:

```python
@dataclass(frozen=True, slots=True)
class SpecialistSpec:
    name: str
    capability_slug: str
    kpi_keys: tuple[str, ...]
    reasoning_focus: str

SPECIALIST_SPECS: dict[str, SpecialistSpec] = {
    "allocation": SpecialistSpec(
        name="Allocation & Tagging Specialist",
        capability_slug="allocation",
        kpi_keys=("unallocated_cost_pct", "allocation_accuracy_index", "shared_cost_apportionment"),
        reasoning_focus="Identify untagged EffectiveCost, infer owners from HippoRAG history, and separate Showback vs Chargeback.",
    ),
    "anomaly": SpecialistSpec(
        name="Anomaly Management Specialist",
        capability_slug="anomaly-management",
        kpi_keys=("daily_service_spikes", "anomaly_unpredicted_variance", "anomaly_cost_avoidance"),
        reasoning_focus="Isolate unexpected EffectiveCost spikes by SubAccountId/ServiceName, filter planned events in HippoRAG, compute Cost Avoidance.",
    ),
    "forecasting": SpecialistSpec(
        name="Forecasting Specialist",
        capability_slug="forecasting",
        kpi_keys=("eom_runrate_forecast", "forecast_accuracy_usage", "forecast_drift_rate"),
        reasoning_focus="Project EOM and quarterly EffectiveCost combining clean historical baseline (excluding one-off anomalies) with client business drivers.",
    ),
    "budgeting": SpecialistSpec(
        name="Budgeting & Variance Specialist",
        capability_slug="budgeting",
        kpi_keys=("budget_burn_rate", "budget_vs_forecast_variance"),
        reasoning_focus="Compare Actual & Forecast EffectiveCost against approved Budgets and Holdbacks (20% Crawl, 15% Walk, 12% Run variance thresholds).",
    ),
    "commitment": SpecialistSpec(
        name="Rate Optimization & Commitments Specialist",
        capability_slug="rate-optimization",
        kpi_keys=("commitment_utilization_score", "commitment_discount_waste_pct", "effective_savings_rate"),
        reasoning_focus="Analyze stable On-Demand baseload (excluding anomalous resources) and existing CUD/SP/RI utilization/waste to propose optimal commitments.",
    ),
}
```

## Causally Ordered Graph Topology

Wire the `StateGraph(FinOpsGraphState)` so upstream context feeds downstream decisions without conflicts:

1. `ingest_and_profile` -> validates CSVs in DuckDB.
2. `allocation` & `anomaly` -> run first; `anomaly` populates `state["active_anomalies"]`.
3. `forecasting` -> consumes `state["active_anomalies"]` to avoid projecting temporary spikes into EOM run-rate.
4. `budgeting` & `commitment` -> consume both `forecasting` and `active_anomalies` so `commitment` never recommends buying a 1-year CUD/Savings Plan for an anomalous spike.
5. `synthesize_report_and_tickets` -> deduplicates findings by `fingerprint`, executes atomic ticket upserts, and writes the executive/engineering Markdown report.
