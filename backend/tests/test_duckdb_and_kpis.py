import pytest
from finops_agent.engine.duckdb_engine import DuckDBFocusEngine
from finops_agent.engine.sql_guard import validate_focus_sql
from finops_agent.engine.kpi_catalog import FILTER

SAFE = "SELECT SUM(EffectiveCost)" + FILTER


@pytest.mark.parametrize("sql", ["DROP TABLE focus_usage", "SELECT * FROM focus_usage", SAFE + "; DROP TABLE focus_usage",
    SAFE.replace("ChargePeriodStart >= $start_utc", "1=1"), SAFE.replace("client_id=$client_id", "1=1"),
    SAFE + " OR 1=1", SAFE.replace("focus_usage", "read_csv('/etc/passwd')"),
    SAFE.replace("BillingCurrency=$currency", "BillingCurrency='USD'"),
    SAFE + " UNION SELECT 1", SAFE.replace("focus_usage", "other_table")])
def test_guard_rejects(sql):
    with pytest.raises(ValueError):
        validate_focus_sql(sql)


def test_guard_accepts():
    assert validate_focus_sql(SAFE) == SAFE


def test_idempotent_ingestion(csv_path, tmp_path):
    engine = DuckDBFocusEngine(":memory:")
    assert engine.ingest_focus_csv("acme", csv_path) == 60
    assert engine.ingest_focus_csv("acme", csv_path) == 0
    altered = tmp_path / "same-rows.csv"
    altered.write_text(csv_path.read_text() + "\n")
    assert engine.ingest_focus_csv("acme", altered) == 0
    assert engine.conn.execute("SELECT COUNT(*) FROM focus_usage").fetchone()[0] == 60
    engine.close()


def test_actual_kpis(container, csv_path):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)
    overview = container.overview("acme")
    values = {m["key"]: m["value"] for m in overview["metrics"]}
    assert len(values) == 13
    assert values["unallocated_cost_pct"] > 0
    assert values["effective_savings_rate"] == pytest.approx((1 - 1 / 1.1) * 100)
    assert values["forecast_accuracy_usage"] is None
    assert values["commitment_utilization_score"] is None
    assert overview["excluded_baseload"] == ["ml-platform:Vertex AI"]
    assert overview["clean_baseload"] == 1710


def test_invalid_csv_rolls_back(container, csv_path, tmp_path):
    invalid = tmp_path / "bad.csv"
    invalid.write_text(csv_path.read_text().replace('2026-10-02', 'not-a-date'))
    client = container.client("acme")
    with pytest.raises(Exception):
        client.engine.ingest_focus_csv("acme", invalid)
    assert client.engine.conn.execute("SELECT count(*) FROM ingested_batches").fetchone()[0] == 0
