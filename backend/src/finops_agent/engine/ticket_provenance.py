"""Server-attributed contributors; historical tickets use recorded traces, never guessed owners."""
import json
from pathlib import Path
from typing import Any
from ..models import FinOpsTicket, TicketContributor

IDENTITY = ("capability", "sub_account_id", "service_name", "period_bucket", "kpi_name")
SPECIALISTS = {"allocation", "anomaly", "forecasting", "budgeting", "commitment"}


def contributors_for(finding: dict[str, Any], traces: list[dict[str, Any]], run_id: str) -> list[TicketContributor]:
    latest = {trace["node"]: trace for trace in traces if trace.get("node") in SPECIALISTS}
    result = [TicketContributor(agent_id=node, role="detected", run_id=run_id)
              for node, trace in latest.items()
              if any(all(item.get(key) == finding.get(key) for key in IDENTITY)
                     for item in trace.get("findings", []))]
    return [*result, TicketContributor(agent_id="orchestrator", role="consolidated", run_id=run_id)]


def historical_contributors(tickets: list[FinOpsTicket], workspace: Path) -> list[dict[str, Any]]:
    documents = [ticket.model_dump() for ticket in tickets]
    missing = [document for document in documents if not document["contributors"]]
    if not missing:
        return documents
    paths = sorted((workspace / "audit_runs").glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths:
        record = json.loads(path.read_text())
        traces = [event["payload"].get("trace") for event in record.get("events", [])]
        traces = [trace for trace in traces if trace]
        synthesis = next((trace for trace in traces if trace.get("node") == "synthesize"), None)
        linked = {item["fingerprint"] for item in synthesis.get("output", {}).get("ticket_links", [])} if synthesis else set()
        for document in missing[:]:
            if document["fingerprint"] in linked:
                document["contributors"] = [item.model_dump() for item in contributors_for(document, traces, record["run_id"])]
                missing.remove(document)
        if not missing:
            break
    return documents
