import os
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from .audit_summaries import CAPABILITY_METRICS, QUERY_INPUTS, decision_summary


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_trace(node: str, started: float, started_at: str, container: Any) -> dict[str, Any]:
    return dict(node=node, status="completed", started_at_utc=started_at, ended_at_utc=timestamp(),
        duration_ms=round((perf_counter()-started)*1000, 3), findings=[], inputs={}, output={},
        metrics=[], rationale=[], query_refs=[], queries=[], context=[], prompt=None, llm_output=None,
        engine="rules", provider="mock" if container.llm is None else type(container.llm).__name__,
        model=getattr(container.llm, "model", os.getenv("FINOPS_LLM_MODEL")) if container.llm is not None else None)


def specialist_trace(name: str, spec: Any, state: dict[str, Any], results: list[dict[str, Any]],
                     started: float, started_at: str, container: Any, llm: dict[str, Any]) -> dict[str, Any]:
    overview = state["kpi_snapshots"]
    trace = base_trace(name, started, started_at, container)
    trace.update(role=spec.reasoning_focus, capability=spec.capability_slug, findings=results,
        inputs=dict(client_id=state["client_id"], period_start_utc=state.get("period_start_utc"),
            period_end_utc=state.get("period_end_utc"), billing_currency="USD",
            prior_findings=state.get("findings", []), active_anomalies=state.get("active_anomalies", []),
            excluded_baseload=overview["excluded_baseload"], profile=overview["profile"],
            derived_inputs={key: overview[key] for key in ("actual", "forecast", "quarterly_forecast",
                "budget", "clean_baseload", "spikes")}),
        metrics=[m for m in overview["metrics"] if m["key"] in CAPABILITY_METRICS[name]],
        query_refs=[q["query_id"] for q in overview.get("query_evidence", []) if q["name"] in QUERY_INPUTS[name]],
        rationale=decision_summary(name, overview, results), output=dict(findings=results),
        report_section="Engineering actions / KPI evidence", **llm)
    if name == "anomaly":
        trace["context"] = [*overview.get("context_evidence", []), *trace["context"]]
    return trace


def append_trace(state: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [*state.get("audit_traces", []), trace]
