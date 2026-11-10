from dataclasses import dataclass
from typing import Any

FILTER = """ FROM focus_usage WHERE client_id=$client_id AND ChargePeriodStart >= $start_utc
 AND ChargePeriodStart < $end_utc AND BillingCurrency=$currency AND ChargeCategory='Usage' """
KPI_SQL_CATALOG = {
    "totals": """SELECT coalesce(sum(EffectiveCost),0) AS actual, sum(ListCost) AS list_cost,
        sum(CASE WHEN ContractedCost > 0 THEN ContractedCost ELSE ListCost END) AS equivalent,
        CASE WHEN count(DISTINCT ConsumedUnit)=1 THEN sum(ConsumedQuantity) ELSE NULL END AS usage, count(DISTINCT CAST(ChargePeriodStart AS DATE)) AS observed_days,
        sum(CASE WHEN CommitmentDiscountStatus='Used' THEN EffectiveCost ELSE 0 END) AS used_commitment,
        sum(CASE WHEN CommitmentDiscountStatus IN ('Used','Unused') THEN EffectiveCost ELSE 0 END) AS commitment,
        sum(CASE WHEN len(list_filter($required_tags, tag ->
          coalesce(json_extract_string(Tags, '/' || tag),'')=''))>0 THEN EffectiveCost ELSE 0 END) AS unallocated,
        sum(CASE WHEN NOT list_contains($shared_accounts,SubAccountId) AND
          len(list_filter($required_tags, tag -> coalesce(json_extract_string(Tags, '/' || tag),'' )=''))=0
          THEN EffectiveCost ELSE 0 END) AS direct,
        sum(CASE WHEN list_contains($shared_accounts,SubAccountId) THEN EffectiveCost ELSE 0 END) AS shared,
        sum(CASE WHEN lower(ServiceCategory) IN ('ai','machine learning','ai and machine learning')
            THEN EffectiveCost ELSE 0 END) AS ai_total""" + FILTER,
    "daily": "SELECT CAST(ChargePeriodStart AS DATE) AS day, sum(EffectiveCost) AS cost" + FILTER + " GROUP BY 1 ORDER BY 1",
    "services": """SELECT SubAccountId AS account, ServiceName AS service,
        ServiceCategory AS category, CAST(ChargePeriodStart AS DATE) AS day,
        sum(EffectiveCost) AS cost,
        sum(CASE WHEN PricingCategory='On-Demand' THEN EffectiveCost ELSE 0 END) AS on_demand"""
        + FILTER + " GROUP BY 1,2,3,4 ORDER BY 4",
}


@dataclass(frozen=True)
class KpiSpec:
    label: str
    capability: str
    formula: str
    unit: str = "%"


KPI_SPECS = {
    "unallocated_cost_pct": KpiSpec("Unallocated cost", "allocation", "Unallocated EffectiveCost / Total EffectiveCost × 100"),
    "allocation_accuracy_index": KpiSpec("Allocation accuracy", "allocation", "Directly attributed EffectiveCost / Total EffectiveCost × 100"),
    "shared_cost_apportionment": KpiSpec("Shared cost apportioned", "allocation", "Apportioned shared cost / Total shared cost × 100"),
    "anomaly_unpredicted_variance": KpiSpec("Unpredicted variance", "anomaly-management", "Anomaly cost − Predicted baseline", "USD"),
    "anomaly_cost_avoidance": KpiSpec("Potential cost avoidance", "anomaly-management", "Correctable daily variance × Remaining days", "USD"),
    "genai_anomaly_detection_rate": KpiSpec("AI anomaly rate", "anomaly-management", "AI anomaly spike cost / Total AI cost × 100"),
    "forecast_accuracy_usage": KpiSpec("Usage forecast error", "forecasting", "(Forecast usage − Actual usage) / Forecast usage × 100"),
    "forecast_drift_rate": KpiSpec("Forecast drift", "forecasting", "(New forecast − Previous forecast) / Previous forecast × 100"),
    "budget_burn_rate": KpiSpec("Daily budget burn", "budgeting", "Actual EffectiveCost / Elapsed calendar days", "USD/day"),
    "budget_vs_forecast_variance": KpiSpec("Budget variance", "budgeting", "(Budget − Forecast) / Budget × 100"),
    "commitment_utilization_score": KpiSpec("Commitment utilization", "rate-optimization", "Used commitment cost / Total commitment cost × 100"),
    "commitment_discount_waste_pct": KpiSpec("Commitment waste", "rate-optimization", "Unused commitment cost / Total commitment cost × 100"),
    "effective_savings_rate": KpiSpec("Effective savings rate", "rate-optimization", "(1 − EffectiveCost / Contracted or list equivalent) × 100"),
}


def metrics(values: dict[str, float | None]) -> list[dict[str, Any]]:
    return [{"key": key, "value": values.get(key), "label": spec.label, "unit": spec.unit,
             "formula": spec.formula, "capability": spec.capability,
             "citation": f"https://www.finops.org/framework/capabilities/{spec.capability}/"}
            for key, spec in KPI_SPECS.items()]
