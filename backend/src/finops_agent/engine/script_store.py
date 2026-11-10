"""Versioned deterministic outputs; these are data artifacts, never agent memory."""
import hashlib
import json
from typing import Any
from uuid import uuid4
from .duckdb_engine import DuckDBFocusEngine
from ..agents.audit_trace import timestamp
from ..config import ROOT

SCRIPT_VERSION = "focus-baseline-v2"


class ScriptStore:
    def __init__(self, engine: DuckDBFocusEngine) -> None:
        self.engine = engine
        with engine.atomic_tx() as tx:
            tx.execute("""CREATE TABLE IF NOT EXISTS script_snapshots
                (snapshot_id VARCHAR PRIMARY KEY, run_id VARCHAR, version VARCHAR,
                 created_at_utc VARCHAR, source_hash VARCHAR, document JSON)""")

    def save(self, overview: dict[str, Any], run_id: str) -> str:
        with self.engine.lock:
            batches = self.engine.conn.execute(
                "SELECT file_hash FROM ingested_batches ORDER BY file_hash").fetchall()
        source = hashlib.sha256(json.dumps(batches).encode()).hexdigest()
        snapshot_id = uuid4().hex
        document = {**overview, "source_hash": source, "script_version": SCRIPT_VERSION,
                    "snapshot_id": snapshot_id, "run_id": run_id, "script_code_hash": script_code_hash()}
        with self.engine.atomic_tx() as tx:
            tx.execute("INSERT INTO script_snapshots VALUES (?,?,?,?,?,?)", [snapshot_id, run_id,
                SCRIPT_VERSION, timestamp(), source, json.dumps(document, default=str)])
        return snapshot_id

    def read(self, snapshot_id: str) -> dict[str, Any]:
        with self.engine.lock:
            row = self.engine.conn.execute(
                "SELECT document FROM script_snapshots WHERE snapshot_id=?", [snapshot_id]).fetchone()
        if not row:
            raise ValueError("Unknown script snapshot")
        return dict(json.loads(row[0]))

    def list(self, run_id: str | None = None) -> list[dict[str, Any]]:
        with self.engine.lock:
            rows = self.engine.conn.execute("""SELECT snapshot_id, run_id, version, created_at_utc,
                source_hash FROM script_snapshots WHERE (? IS NULL OR run_id=?) ORDER BY created_at_utc DESC LIMIT 100""",[run_id,run_id]).fetchall()
        keys = ("snapshot_id", "run_id", "version", "created_at_utc", "source_hash")
        return [dict(zip(keys, row)) for row in rows]


def script_code_hash() -> str:
    directory = ROOT / "backend/src/finops_agent/engine"
    digest = hashlib.sha256()
    for name in ("analytics.py", "kpi_catalog.py", "context.py"):
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()
