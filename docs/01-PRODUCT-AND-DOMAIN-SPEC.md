# 01 — Product & FinOps Domain Specification

## 1. System Purpose
`finops-agent-app` is an autonomous FinOps multi-agent platform that ingests daily cloud billing exports in **FOCUS** format (`.csv`), builds a **Dual HippoRAG** associative memory (canonical FinOps Foundation guidelines + episodic client context & tickets), executes guarded **DuckDB** SQL analytics across **5 Specialist Agents** orchestrated by **LangGraph**, and outputs executive/engineering reports plus deduplicated, atomic **Tickets (`FIN-XXX.md`)**.

## 2. Canonical FinOps Capabilities & References
Every module, query, report, and ticket in this application maps to the local knowledge base at `finops_capabilities_md/capabilities/<slug>.md`:

| Module / Specialist | Capability Slug | Local Spec | Official URL |
|---|---|---|---|
| CSV Loader & Validator | `data-ingestion` | `@finops_capabilities_md/capabilities/data-ingestion.md` | https://www.finops.org/framework/capabilities/data-ingestion/ |
| Allocation Specialist | `allocation` | `@finops_capabilities_md/capabilities/allocation.md` | https://www.finops.org/framework/capabilities/allocation/ |
| Anomaly Specialist | `anomaly-management` | `@finops_capabilities_md/capabilities/anomaly-management.md` | https://www.finops.org/framework/capabilities/anomaly-management/ |
| Forecasting Specialist | `forecasting` | `@finops_capabilities_md/capabilities/forecasting.md` | https://www.finops.org/framework/capabilities/forecasting/ |
| Budgeting Specialist | `budgeting` | `@finops_capabilities_md/capabilities/budgeting.md` | https://www.finops.org/framework/capabilities/budgeting/ |
| Commitment Specialist | `rate-optimization` | `@finops_capabilities_md/capabilities/rate-optimization.md` | https://www.finops.org/framework/capabilities/rate-optimization/ |
| Report & UI Views | `reporting-analytics` | `@finops_capabilities_md/capabilities/reporting-analytics.md` | https://www.finops.org/framework/capabilities/reporting-analytics/ |
| Ticket Loop & Engine | `automation-tools-services` | `@finops_capabilities_md/capabilities/automation-tools-services.md` | https://www.finops.org/framework/capabilities/automation-tools-services/ |

## 3. Core Workflows

### Workflow A: Client Onboarding (`mode = "onboarding"`)
1. **Inputs**: Historical FOCUS CSV exports (30–90 days), initial `client_profile.yaml` (or basic metadata: `client_id`, `niche`, `billing_currency`, `allocation_model` [`Showback` | `Chargeback`], required tags), and optional unstructured `context_notes/*.md`.
2. **Execution**:
   - Ingests CSVs idempotently into DuckDB (`focus_usage`).
   - Runs baseline profiling across all 5 specialists.
   - Proposes initial monthly/quarterly **Budgets** and **Holdback %**, baseline **EOM Forecast**, initial **Tagging taxonomy remediation tickets**, and **Commitment coverage baseline**.
   - Persists baseline context into `workspaces/<client_id>/` and indexes into `client_<id>_graph` (HippoRAG).

### Workflow B: Daily FinOps Cycle (`mode = "daily"`)
1. **Inputs**: New daily FOCUS CSV export(s) + current `client_profile.yaml` + existing `tickets_ledger` & `client_<id>_graph`.
2. **Causal Execution Order**:
   - **Step 1 (`ingest_and_profile`)**: Validates and loads new CSV partitions idempotently.
   - **Step 2 (`allocation` + `anomaly`)**: Runs first. Detects untagged spend and statistical `EffectiveCost` spikes. Cross-references `client_<id>_graph` in HippoRAG to suppress planned spikes (e.g., approved GPU training tickets). Emits `active_anomalies`.
   - **Step 3 (`forecasting`)**: Projects EOM and rolling quarterly `EffectiveCost`, excluding one-off `active_anomalies` and incorporating planned business drivers from HippoRAG.
   - **Step 4 (`budgeting` + `commitment`)**:
     - `budgeting` compares Actual + Forecast vs. Approved Budget & Holdback (thresholds: **20% Crawl**, **15% Walk**, **12% Run**).
     - `commitment` analyzes stable `On-Demand` baseload (strictly excluding `active_anomalies`) and existing `CommitmentDiscountId` utilization/waste.
   - **Step 5 (`synthesize_report_and_tickets`)**: Deduplicates findings by SHA-256 `fingerprint`, atomically writes new `FIN-XXX.md` tickets, updates `tickets_ledger`, indexes new tickets into HippoRAG, and writes the daily Markdown report.

### Workflow C: Bidirectional Ticket Feedback Loop
1. User updates a ticket in the UI (`PROPOSED` -> `APPROVED` | `IMPLEMENTED` | `REJECTED` | `FALSE_POSITIVE` | `SNOOZED`) and adds a resolution note.
2. Backend atomically updates `tickets/FIN-XXX.md`, DuckDB `tickets_ledger`, and re-indexes the passage in `client_<id>_graph` (HippoRAG).
3. Subsequent daily runs automatically recall this decision via HippoRAG associative retrieval.

## 4. Official FinOps Foundation KPI Catalog & Formulas
All queries filter by `client_id = $client_id`, `ChargePeriodStart >= $start_utc AND ChargePeriodStart < $end_utc`, and `BillingCurrency = $currency` (Timezone: `UTC`).

| KPI Key | Capability | Official Formula |
|---|---|---|
| `unallocated_cost_pct` | `allocation` | `(SUM(EffectiveCost WHERE required_tags_missing) / SUM(EffectiveCost)) * 100` |
| `allocation_accuracy_index` | `allocation` | `(SUM(EffectiveCost WHERE directly_attributed) / SUM(EffectiveCost)) * 100` |
| `shared_cost_apportionment` | `allocation` | `(SUM(ApportionedSharedEffectiveCost) / SUM(TotalSharedEffectiveCost)) * 100` |
| `anomaly_unpredicted_variance` | `anomaly-management` | `SUM(AnomalyEventEffectiveCost) - SUM(BaselinePredictedEffectiveCost)` |
| `anomaly_cost_avoidance` | `anomaly-management` | `UnpredictedCorrectableDailySpend * ProjectedDaysRemainingInPeriod` |
| `genai_anomaly_detection_rate` | `anomaly-management` | `SUM(AIAnomalySpikeCost) / SUM(TotalAISpend)` (`<2%` Green, `2-7%` Yellow, `>7%` Red) |
| `forecast_accuracy_usage` | `forecasting` | `((ForecastedUsageQuantity - ActualUsageQuantity) / ForecastedUsageQuantity) * 100` |
| `forecast_drift_rate` | `forecasting` | `((NewForecastSpend - PreviousForecastSpend) / PreviousForecastSpend) * 100` |
| `budget_burn_rate` | `budgeting` | `SUM(ActualEffectiveCost) / DaysElapsedInPeriod` |
| `budget_vs_forecast_variance` | `budgeting` | `((BudgetedEffectiveCost - ForecastedEffectiveCost) / BudgetedEffectiveCost) * 100` |
| `commitment_utilization_score` | `rate-optimization` | `(SUM(UsedCommitmentCost) / SUM(TotalCommitmentCost)) * 100` |
| `commitment_discount_waste_pct` | `rate-optimization` | `(SUM(UnusedCommitmentCost) / SUM(TotalCommitmentCost)) * 100` |
| `effective_savings_rate` | `rate-optimization` | `(1 - (SUM(EffectiveCost) / SUM(ContractedOrListOnDemandEquivalentCost))) * 100` |
