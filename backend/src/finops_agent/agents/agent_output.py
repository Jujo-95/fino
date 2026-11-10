from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from ..models import Finding
from .tool_catalog import tool
from ..engine.kpi_catalog import KPI_SPECS


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_key: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    title: str = Field(min_length=1, max_length=160)
    justification: str = Field(min_length=1, max_length=2000)
    recommended_action: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=3, max_length=12)


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=12000)
    proposals: list[Proposal] = Field(max_length=3)
    evidence_ids: list[str] = Field(min_length=3, max_length=20)


def submit_tool(spec: Any, available: list[dict[str, Any]]) -> dict[str, Any]:
    schema = AgentOutput.model_json_schema()
    allowed = [metric["key"] for metric in available if metric["capability"] == spec.capability_slug
               and metric["value"] is not None]
    schema["$defs"]["Proposal"]["properties"]["metric_key"]["enum"] = allowed or list(KPI_SPECS)
    if not allowed:
        schema["properties"]["proposals"]["maxItems"] = 0
    result = tool("submit_analysis", "Submit final auditable conclusions after querying data and scripts. "
                  "Use metric_key from scripts; do not invent amounts or calculate in prose.", {}, [])
    result["function"]["parameters"] = schema
    return result


def validate_output(args: dict[str, Any], tools: Any, spec: Any) -> AgentOutput:
    result = AgentOutput.model_validate(args)
    if not tools.queries or not any(key.startswith("script:") for key in tools.evidence):
        raise ValueError("Must call query_focus and read_scripts before submitting")
    if not any(key.startswith("context:") for key in tools.evidence):
        raise ValueError("Must read client context before submitting")
    if len({p.metric_key for p in result.proposals}) != len(result.proposals):
        raise ValueError("Merge proposals for the same metric into one actionable finding")
    metrics = {m["key"]: m for m in tools.state["kpi_snapshots"]["metrics"]}
    if spec.capability_slug == "orchestrator" and result.proposals:
        raise ValueError("Orchestrator consolidates specialist proposals; cannot create its own")
    for proposal in result.proposals:
        metric = metrics.get(proposal.metric_key)
        if not metric or metric["capability"] != spec.capability_slug or metric["value"] is None:
            raise ValueError("Proposal must reference an available metric in your capability. Allowed: " +
                ", ".join(key for key, value in metrics.items() if value["capability"] == spec.capability_slug
                          and value["value"] is not None))
        check_refs(proposal.evidence_ids, tools)
    check_refs(result.evidence_ids, tools)
    return result


def check_refs(refs: list[str], tools: Any) -> None:
    if any(ref not in tools.evidence for ref in refs):
        raise ValueError("Unknown evidence_id; cite only returned tool evidence")
    if not any(ref in {q["query_id"] for q in tools.queries} for ref in refs):
        raise ValueError("Each conclusion must cite an executed SQL query")
    if not any(ref.startswith("context:") for ref in refs):
        raise ValueError("Cite the client context evidence_id used for policy interpretation")
    if not any(ref.startswith("script:") for ref in refs):
        raise ValueError("Each conclusion must cite the metric script snapshot")


def findings_from_output(output: AgentOutput, tools: Any, spec: Any) -> list[Finding]:
    overview = tools.state["kpi_snapshots"]
    profile = tools.client.profile
    metrics = {m["key"]: m for m in overview["metrics"]}
    return [Finding(capability=spec.capability_slug, maturity_tier=profile.target_maturity,
        allocation_mode=profile.allocation_policy.mode if spec.capability_slug == "allocation" else "N/A",
        severity=p.severity, sub_account_id="all", service_name="all",
        period_bucket=tools.state["period_start_utc"][:7], kpi_name=p.metric_key,
        kpi_value=metrics[p.metric_key]["value"], estimated_monthly_impact_usd=None,
        title=p.title, evidence_summary=p.justification + " Evidence: " + ", ".join(p.evidence_ids),
        recommended_action=p.recommended_action, capability_citation_url=metrics[p.metric_key]["citation"])
        for p in output.proposals]
