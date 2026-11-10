from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpecialistSpec:
    name: str
    capability_slug: str
    kpi_keys: tuple[str, ...]
    reasoning_focus: str


SPECIALIST_SPECS = {
    "allocation": SpecialistSpec("Allocation", "allocation", ("unallocated_cost_pct",),
        "Identify missing required tags. Preserve Showback versus Chargeback semantics."),
    "anomaly": SpecialistSpec("Anomaly", "anomaly-management", ("anomaly_unpredicted_variance",),
        "Distinguish unexpected cost spikes from planned events and resolved false positives."),
    "forecasting": SpecialistSpec("Forecasting", "forecasting", ("forecast_drift_rate",),
        "Project month-end and quarter using a clean baseline and approved business drivers."),
    "budgeting": SpecialistSpec("Budgeting", "budgeting", ("budget_vs_forecast_variance",),
        "Compare forecast to approved budget and holdback with maturity thresholds."),
    "commitment": SpecialistSpec("Commitments", "rate-optimization", ("commitment_discount_waste_pct",),
        "Exclude every detected spike from stable on-demand baseload and respect term constraints."),
}
