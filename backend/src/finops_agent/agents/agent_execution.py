import json
from time import perf_counter
from typing import Any
from .audit_trace import append_trace, specialist_trace, timestamp
from .agent_output import findings_from_output
from .prompts import system_prompt, prompt_hash
from .query_tools import AgentTools
from .incremental import history_for_node
from .specs import SPECIALIST_SPECS
from .tool_loop import run_loop


async def execute_specialist(container: Any, spec: Any, state: Any) -> dict[str, Any]:
    started, started_at = perf_counter(), timestamp()
    node = next(name for name, item in SPECIALIST_SPECS.items() if item == spec)
    tools = AgentTools(container, dict(state), node)
    messages = [dict(role="system", content=system_prompt(spec)), dict(role="user", content=json.dumps(dict(
        client_id=state["client_id"], period_start_utc=state["period_start_utc"],
        period_end_utc=state["period_end_utc"], prior_findings=state.get("findings", []),
        refinement=state.get("refinement", ""), instruction=state.get("instruction", ""),
        history=history_for_node(dict(state), spec.capability_slug), force_reason=state.get("force_reason", "")), default=str))]
    try:
        async with container.llm_semaphore:
            result = await run_loop(container.llm, messages, tools, spec)
    except Exception as exc:
        persist_failure(container, state, node, tools, messages, str(exc))
        raise
    output = result["output"]
    findings = [finding.model_dump() for finding in findings_from_output(output, tools, spec)]
    trace = specialist_trace(node, spec, dict(state), findings, started, started_at, container, {})
    trace.update(engine="llm_agent", model=", ".join(result.get("models",[])) or container.llm.model, queries=tools.queries,
        query_refs=[q["query_id"] for q in tools.queries], rationale=[output.summary],
        output=output.model_dump(), llm_output=output.summary, prompt=dict(messages=result["messages"]),
        tool_calls=tools.calls, usage=result["usage"], context=context_documents(tools),
        prompt_hash=prompt_hash(messages[0]["content"]), execution_config=container.llm.audit_config(),
        tool_definitions=result["tool_definitions"])
    update = dict(findings=[*state.get("findings", []), *findings],
        specialist_commentary={**state.get("specialist_commentary", {}), spec.name: output.summary},
        audit_traces=append_trace(dict(state), trace))
    if node == "anomaly":
        update.update(active_anomalies=[row["key"] for row in state["kpi_snapshots"]["spikes"]],
                      excluded_baseload=state["kpi_snapshots"]["excluded_baseload"])
    return update


def context_documents(tools: AgentTools) -> list[dict[str, Any]]:
    return [doc for item in tools.evidence.values() for doc in item.get("documents", [])]


def persist_failure(container: Any, state: Any, node: str, tools: AgentTools,
                    messages: list[dict[str, Any]], error: str) -> None:
    from ..engine.run_audit import RunAuditStore
    if state.get("run_id"):
        store = RunAuditStore(container.client(state["client_id"]).workspace)
        record = store.read(state["run_id"])
        record["partial_failure"] = dict(node=node, queries=tools.queries, tool_calls=tools.calls,
                                         messages=messages, error=error)
        store.save(record)
