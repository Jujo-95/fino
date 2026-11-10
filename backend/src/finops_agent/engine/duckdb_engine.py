import hashlib
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
import duckdb
from .schema import COLUMNS, DDL, KEYS, REQUIRED, LEDGER_FIELDS
from .sql_guard import validate_focus_sql


class DuckDBFocusEngine:
    def __init__(self, db_path: Path | str) -> None:
        self.lock = threading.RLock()
        self.conn = duckdb.connect(str(db_path))
        self.conn.execute("SET threads=2")
        self.conn.execute("SET memory_limit='512MB'")
        self.conn.execute("SET TimeZone='UTC'")
        self.conn.execute(DDL)
        legacy = self.conn.execute("SELECT 1 FROM information_schema.tables WHERE table_name='graph_documents'").fetchone()
        if legacy:
            self.conn.execute("INSERT INTO context_documents SELECT * FROM graph_documents ON CONFLICT DO NOTHING")
        for name, kind in LEDGER_FIELDS.items():
            self.conn.execute(f"ALTER TABLE tickets_ledger ADD COLUMN IF NOT EXISTS {name} {kind}")
            self.conn.execute(f"UPDATE tickets_ledger SET {name}=CAST(json_extract_string(document, '/{name}') AS {kind}) "
                              f"WHERE {name} IS NULL")
        fields = ",".join(f'"{key}" {kind}' for key, kind in COLUMNS.items())
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS focus_usage (client_id VARCHAR, file_hash VARCHAR, "
                          f"row_key VARCHAR, {fields}, PRIMARY KEY(client_id,row_key))")
        for name, kind in COLUMNS.items():
            self.conn.execute(f'ALTER TABLE focus_usage ADD COLUMN IF NOT EXISTS "{name}" {kind}')

    @contextmanager
    def atomic_tx(self) -> Iterator[duckdb.DuckDBPyConnection]:
        with self.lock:
            self.conn.execute("BEGIN TRANSACTION")
            try:
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    def ingest_focus_csv(self, client_id: str, csv_path: Path) -> int:
        with csv_path.open("rb") as source:
            file_hash = hashlib.file_digest(source, "sha256").hexdigest()
        with self.atomic_tx() as tx:
            if tx.execute("SELECT 1 FROM ingested_batches WHERE client_id=? AND file_hash=?",
                          [client_id, file_hash]).fetchone():
                return 0
            tx.execute("CREATE OR REPLACE TEMP TABLE incoming AS SELECT * FROM read_csv_auto(?, all_varchar=true)",
                       [str(csv_path)])
            return self.ingest_prepared(client_id, file_hash, csv_path.name)

    def ingest_prepared(self, client_id: str, file_hash: str, filename: str) -> int:
        """Validate incoming in the caller's transaction; shared by local and S3 ingestion."""
        if self.conn.execute("SELECT 1 FROM ingested_batches WHERE client_id=? AND file_hash=?",
                             [client_id,file_hash]).fetchone():
            return 0
        present = {row[0] for row in self.conn.execute("DESCRIBE incoming").fetchall()}
        if not REQUIRED <= present:
            raise ValueError(f"Missing FOCUS columns: {sorted(REQUIRED - present)}")
        self._normalize(present)
        self._validate_rows()
        return self._insert(client_id,file_hash,filename)

    def _normalize(self, present: set[str]) -> None:
        fields = [f'CAST("{key}" AS {kind}) AS "{key}"' if key in present else
                  f'CAST(NULL AS {kind}) AS "{key}"'
                  for key, kind in COLUMNS.items()]
        self.conn.execute("CREATE OR REPLACE TEMP TABLE normalized AS SELECT " + ",".join(fields) + " FROM incoming")

    def _validate_rows(self) -> None:
        bad = self.conn.execute("""SELECT count(*) FROM normalized WHERE
            ChargePeriodStart IS NULL OR ChargePeriodEnd <= ChargePeriodStart OR ChargePeriodEnd IS NULL
            OR BillingPeriodStart IS NULL OR EffectiveCost IS NULL OR NOT isfinite(EffectiveCost)
            OR BillingCurrency IS NULL OR SubAccountId IS NULL OR ServiceName IS NULL
            OR BilledCost IS NULL OR NOT isfinite(BilledCost) OR ListCost IS NULL OR NOT isfinite(ListCost)
            OR ContractedCost IS NULL OR NOT isfinite(ContractedCost)
            OR BillingAccountId IS NULL OR ChargeCategory IS NULL OR PricingCategory IS NULL
            OR ServiceCategory IS NULL OR json_type(Tags) != 'OBJECT' OR Tags IS NULL""").fetchone()
        if bad and bad[0]:
            raise ValueError("Invalid FOCUS timestamps, cost, tags or identity fields")

    def _insert(self, client: str, digest: str, filename: str) -> int:
        identity = ",".join(f'coalesce(CAST("{key}" AS VARCHAR),'')' for key in KEYS)
        before_row = self.conn.execute("SELECT count(*) FROM focus_usage").fetchone()
        before = before_row[0] if before_row else 0
        self.conn.execute(f"INSERT OR REPLACE INTO focus_usage (client_id,file_hash,row_key,{','.join(COLUMNS)}) SELECT ?, ?, sha256(to_json(list_value({identity}))), "
                          "* FROM normalized", [client, digest])
        after_row = self.conn.execute("SELECT count(*) FROM focus_usage").fetchone()
        count = (after_row[0] if after_row else 0) - before
        self.conn.execute("INSERT INTO ingested_batches(client_id,file_hash,file_name,row_count) VALUES (?,?,?,?)",
                          [client, digest, filename, count])
        return int(count)

    def query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        validate_focus_sql(sql)
        with self.lock:
            cursor = self.conn.execute(sql, params)
            names = [item[0] for item in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def bounded_query(self, sql: str, params: dict[str, Any], seconds: float = 15) -> list[dict[str, Any]]:
        with self.lock:
            timer = threading.Timer(seconds, self.conn.interrupt)
            timer.daemon = True
            timer.start()
            try:
                return self.query(sql, params)
            finally:
                timer.cancel()
                timer.join()

    def close(self) -> None:
        self.conn.close()
