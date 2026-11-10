---
name: finops-build-duckdb-engine
description: Build and extend the idempotent DuckDB FOCUS SQL engine, CSV ingestion pipeline, sqlglot AST validator, and official FinOps KPI query catalog. Use whenever creating or modifying DuckDB storage, FOCUS CSV ingestion, SQL validation, or KPI queries.
---

# FinOps DuckDB & FOCUS Engine Skill

## Capabilities Covered
- `@finops_capabilities_md/capabilities/data-ingestion.md` (https://www.finops.org/framework/capabilities/data-ingestion/)
- `@finops_capabilities_md/capabilities/reporting-analytics.md` (https://www.finops.org/framework/capabilities/reporting-analytics/)

## Core Blueprint (Extend, Don't Repeat)

### 1. Atomic & Idempotent FOCUS CSV Ingestion
Never load CSVs into Pandas. Stream directly via DuckDB inside an explicit transaction keyed by `file_sha256` and `BillingPeriodStart`:

```python
from contextlib import contextmanager
import hashlib
from pathlib import Path
import duckdb

class DuckDBFocusEngine:
    def __init__(self, db_path: Path) -> None:
        self.conn = duckdb.connect(str(db_path))
        self._init_schema()

    @contextmanager
    def atomic_tx(self):
        self.conn.execute("BEGIN TRANSACTION")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def ingest_focus_csv(self, client_id: str, csv_path: Path) -> int:
        file_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()[:16]
        with self.atomic_tx() as tx:
            already = tx.execute(
                "SELECT 1 FROM ingested_batches WHERE client_id = $1 AND file_hash = $2",
                [client_id, file_hash],
            ).fetchone()
            if already:
                return 0  # Idempotent no-op
            tx.execute(
                """
                INSERT OR REPLACE INTO focus_usage
                SELECT $1 AS client_id, $2 AS file_hash, *
                FROM read_csv_auto($3, header=true, normalize_names=false)
                """,
                [client_id, file_hash, str(csv_path)],
            )
            tx.execute(
                "INSERT INTO ingested_batches VALUES ($1, $2, current_timestamp)",
                [client_id, file_hash],
            )
            return tx.execute(
                "SELECT COUNT(*) FROM focus_usage WHERE client_id = $1 AND file_hash = $2",
                [client_id, file_hash],
            ).fetchone()[0]
```

### 2. SQL AST Guardrail (`sqlglot`)
Every dynamic or template SQL query must pass `validate_focus_sql(sql)` before running:

```python
import sqlglot
from sqlglot import exp

def validate_focus_sql(sql: str) -> str:
    parsed = sqlglot.parse_one(sql, read="duckdb")
    if not isinstance(parsed, exp.Select):
        raise ValueError("Only read-only SELECT statements are allowed.")
    sql_upper = sql.upper()
    if "CHARGEPERIODSTART" not in sql_upper:
        raise ValueError("Missing mandatory partition filter on ChargePeriodStart.")
    if "BILLINGCURRENCY" not in sql_upper:
        raise ValueError("Missing mandatory BillingCurrency filter or grouping.")
    return sql
```

### 3. Single Parametrized KPI Registry
Do not write separate Python functions per KPI. Register all official FinOps Foundation KPIs in a single `KPI_SQL_CATALOG: dict[str, str]` using `$client_id`, `$start_utc`, `$end_utc`, and `$currency` bindings:
- `unallocated_cost_pct` (`Allocation`)
- `allocation_accuracy_index` (`Allocation`)
- `anomaly_unpredicted_variance` (`Anomaly Management`)
- `forecast_eom_runrate` (`Forecasting`)
- `budget_burn_rate_and_variance` (`Budgeting`)
- `commitment_utilization_and_esr` (`Rate Optimization`)
