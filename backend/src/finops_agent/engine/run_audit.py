import json
import builtins
import re
from pathlib import Path
from typing import Any
from uuid import uuid4
from ..config import atomic_write_text
from ..agents.audit_trace import timestamp


class RunAuditStore:
    def __init__(self, workspace: Path) -> None:
        self.directory = workspace / "audit_runs"

    def create(self, body: dict[str, Any], provider: str) -> dict[str, Any]:
        record = dict(run_id=body.get('run_id') or uuid4().hex, client_id=body["client_id"], run_mode=body["run_mode"],
            created_at_utc=timestamp(), finished_at_utc=None, status="running", provider=provider,
            period_start_utc=body["period_start_utc"], period_end_utc=body["period_end_utc"],
            billing_currency=body["billing_currency"], events=[], report_markdown="", error=None,
            failed_node=None, queries=[], schema_version=2, instruction=body.get("instruction", ""),
            reference_run_id=body.get("reference_run_id"), force_reanalysis=body.get("force_reanalysis", False),
            force_reason=body.get("force_reason", ""))
        self.save(record)
        return record

    def save(self, record: dict[str, Any]) -> None:
        atomic_write_text(self.path(record["run_id"]), json.dumps(record, default=str, ensure_ascii=False))

    def path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Invalid run_id")
        return self.directory / (run_id + ".json")

    def read(self, run_id: str) -> dict[str, Any]:
        path = self.path(run_id)
        if not path.exists():
            raise KeyError("Execution audit not found")
        record: dict[str, Any] = json.loads(path.read_text())
        return record

    def list(self, limit: int | None = 100) -> list[dict[str, Any]]:
        paths = sorted(self.directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
        keys = ("run_id", "client_id", "run_mode", "created_at_utc", "finished_at_utc", "status",
                "provider", "period_start_utc", "period_end_utc")
        return [{**{key: record[key] for key in keys},'analysis_only':record.get('analysis_only',False)} for path in paths
                for record in [json.loads(path.read_text())]]

    def detail(self, run_id: str) -> dict[str, Any]:
        record = self.read(run_id)
        if record.get("reused_run_id"):
            record["report_markdown"] = self.read(record["reused_run_id"])["report_markdown"]
        return record

    def reports(self) -> builtins.list[dict[str, str]]:
        paths = sorted(self.directory.glob("*.json"), key=lambda path:path.stat().st_mtime, reverse=True)
        return [dict(name=record.get("report_file", record["run_id"]+".md"), markdown=record["report_markdown"],
                     created_at_utc=record["created_at_utc"], outcome=record.get("incremental", {}).get("outcome", ""))
                for path in paths for record in [json.loads(path.read_text())]
                if record["status"] == "completed" and record.get("report_markdown") and not record.get("reused_run_id")]

    def capture(self, record: dict[str, Any], node: str, payload: dict[str, Any]) -> None:
        trace = next((trace for trace in reversed(payload.get("audit_traces", [])) if trace["node"] == node), None)
        if node == "synthesize" and trace:
            for revision in trace.get("refinements", []):
                revised = revision["trace"]
                previous = next((event for event in record["events"] if event["node"] == revised["node"]), None)
                if previous:
                    previous.setdefault("revision_history", []).append(previous["payload"]["trace"])
                    previous["payload"]["trace"] = revised
        record["events"].append(dict(node=node, payload={"trace": trace}))
        if node == "ingest_and_profile":
            record["queries"] = list(payload["kpi_snapshots"].get("query_evidence", []))
        if trace and node != "ingest_and_profile":
            record["queries"].extend(trace.get("queries", []))
        for key in ("input_signature", "reference_run_id", "incremental", "reused_run_id", "report_file"):
            if key in payload:
                record[key] = payload[key]
        if node == "synthesize" and not payload.get("reused_run_id"):
            record["report_markdown"] = payload.get("report_markdown", "")
        self.save(record)

    def finish(self, record: dict[str, Any], status: str, error: str | None = None) -> None:
        record.update(status=status, error=error, finished_at_utc=timestamp())
        self.save(record)
