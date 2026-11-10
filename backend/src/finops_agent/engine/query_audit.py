from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4
from .duckdb_engine import DuckDBFocusEngine
from .kpi_catalog import KPI_SQL_CATALOG


def query_with_evidence(engine: DuckDBFocusEngine, name: str, params: dict[str, Any],
                        evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    started = perf_counter()
    sql = KPI_SQL_CATALOG[name]
    rows = engine.query(sql, params)
    evidence.append(dict(query_id=uuid4().hex, name=name, sql=sql, parameters=params,
        executed_by="ingest_and_profile", source="script", executed_at_utc=datetime.now(timezone.utc).isoformat(),
        duration_ms=round((perf_counter()-started)*1000, 3), row_count=len(rows),
        sample_rows=rows[:100], sample_limit=100, truncated=len(rows)>100, status="completed"))
    return rows
