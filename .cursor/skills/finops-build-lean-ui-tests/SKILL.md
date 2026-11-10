---
name: finops-build-lean-ui-tests
description: Build and extend the React + TypeScript FinOps Dashboard and the table-driven pytest verification suite. Use whenever creating or modifying frontend components, hooks, or backend unit and integration tests.
---

# FinOps Lean UI & Table-Driven Testing Skill

## Capabilities Covered
- `@finops_capabilities_md/capabilities/reporting-analytics.md` (https://www.finops.org/framework/capabilities/reporting-analytics/)
- `@finops_capabilities_md/capabilities/invoicing-chargeback.md` (https://www.finops.org/framework/capabilities/invoicing-chargeback/)

## 1. Lean Frontend Blueprint (React + TypeScript)
Keep the entire dashboard in 4 composable views backed by a single `useSSEStream` hook and reusable cards:
1. **`OnboardingPanel`**: Uploads initial FOCUS CSVs + `client_profile.yaml` (`BillingCurrency`, `UTC`, **Showback** vs **Chargeback** policy, initial budgets/holdbacks).
2. **`LiveOrchestratorConsole`**: Connects to `/runs/stream` via SSE and shows real-time progress across the 5 Specialist Agents.
3. **`KpiOverviewGrid`**: Renders a single generic `<KpiCard />` mapped over the official FinOps KPIs (with formula tooltip, maturity badge `Crawl | Walk | Run`, and currency).
4. **`TicketsKanbanBoard`**: Lists generated `FIN-XXX` tickets (`PROPOSED`, `APPROVED`, `IMPLEMENTED`, `FALSE_POSITIVE`). Updating a ticket status or adding a resolution comment calls `PATCH /tickets/{id}` which atomically updates the `.md`, DuckDB ledger, and HippoRAG client memory.

## 2. Table-Driven Pytest Blueprint (Zero Test Bloat)
Every test file must validate real invariants (idempotency, atomicity, SQL guardrails, KPI formulas) using `@pytest.mark.parametrize`:

```python
@pytest.mark.parametrize(
    "sql,should_pass",
    [
        ("SELECT SUM(EffectiveCost), BillingCurrency FROM focus_usage WHERE ChargePeriodStart >= '2026-10-01' GROUP BY 2", True),
        ("SELECT SUM(EffectiveCost) FROM focus_usage", False),  # Missing ChargePeriodStart & BillingCurrency
        ("DROP TABLE focus_usage", False),                      # Mutation blocked
    ],
)
def test_sql_ast_guardrail(sql: str, should_pass: bool) -> None:
    if should_pass:
        assert validate_focus_sql(sql) == sql
    else:
        with pytest.raises(ValueError):
            validate_focus_sql(sql)

def test_idempotent_csv_ingestion_and_ticket_upsert(tmp_path: Path, sample_focus_csv: Path) -> None:
    engine = DuckDBFocusEngine(tmp_path / "test.duckdb")
    first_count = engine.ingest_focus_csv("acme", sample_focus_csv)
    second_count = engine.ingest_focus_csv("acme", sample_focus_csv)
    assert first_count > 0
    assert second_count == 0  # Strictly idempotent
```
