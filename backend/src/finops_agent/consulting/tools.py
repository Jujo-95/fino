from typing import Any, Literal
from langchain_core.tools import tool
from .models import ContextProposal, ContextValues
from .store import ConsultingStore
from .diagnosis import diagnosis
from .agenda import agenda
from .verification import verifications
from .supporting import supporting_data


def consulting_tools(ctx: Any, internal: bool = False) -> list[Any]:
    @tool
    def simulate_cloud_action(provider: Literal['aws', 'gcp', 'azure'], operation: str,
        target: str, parameters: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        """Prepare a cloud action without changing resources. Returns a stable idempotent proposal for user approval."""
        from .action_connectors import CloudActionRequest, simulate
        result = simulate(ctx.client, CloudActionRequest(provider=provider, operation=operation, target=target,
            parameters=parameters or {}, idempotency_key=idempotency_key))
        return ctx.record('simulate_cloud_action', result)
    @tool
    def read_diagnosis() -> dict[str, Any]:
        """Read current tenant-scoped capability evidence, missing inputs and confirmed context. Never a global health score."""
        return ctx.record('read_diagnosis', diagnosis(ctx.client))
    @tool
    def read_confirmed_context() -> dict[str, Any]:
        """Read user-confirmed scope, account owners, budget, objectives and constraints with revision. Defaults are unconfirmed."""
        return ctx.record('read_confirmed_context', ConsultingStore(ctx.client).context())
    @tool
    def read_action_plan() -> dict[str, Any]:
        """Read the same prioritized daily agenda as dashboard/tickets; includes independent urgent actions and blockers."""
        from .progress import agent_progress
        value = agenda(ctx.client)
        value['progress'] = agent_progress(value['progress'])
        return ctx.record('read_action_plan', value)
    @tool
    def read_action_verification() -> dict[str, Any]:
        """Read implementation follow-up. Observed reductions are not attributable savings; no cloud changes executed."""
        return ctx.record('read_action_verification', dict(verifications=verifications(ctx.client)))
    @tool
    def read_supporting_data() -> dict[str, Any]:
        """Read tenant-scoped utilization observations and commitment terms with dates and provenance. Check relevance and recency before recommending."""
        return ctx.record('read_supporting_data', supporting_data(ctx.client))
    @tool
    def record_capability_assessment(capability: str, conclusion: Literal['NO_ISSUES_DETECTED','ATTENTION_REQUIRED','FOLLOW_UP'], summary: str, evidence_refs: list[str]) -> dict[str, Any]:
        """Persist a scoped analytical conclusion backed by this turn's real finance query. Not user authorization; no ticket/context mutations. Missing inputs prevent declaring no issues."""
        from .review import record_review
        return ctx.record('record_capability_assessment',record_review(ctx,capability,conclusion,summary,evidence_refs))
    @tool
    def propose_context_changes(values: ContextValues, reason: str, expected_revision: str | None = None) -> dict[str, Any]:
        """Prepare a proposal ONLY from explicit user statements. Backend binds the context revision from its verified read; omit expected_revision. Does not apply it. User confirms in the proposal card."""
        from .proposal_scope import proposal_revision
        result = ConsultingStore(ctx.client).propose(ContextProposal(expected_revision=proposal_revision(ctx,expected_revision),
            values=values, reason=reason), 'chat:'+ctx.thread_id)
        return ctx.record('propose_context_changes', result)
    reads = [read_diagnosis, read_confirmed_context, read_action_plan, read_action_verification, read_supporting_data,
             record_capability_assessment]
    return reads if internal else [*reads, propose_context_changes, simulate_cloud_action]
