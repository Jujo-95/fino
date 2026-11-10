from typing import Any, Literal
from langchain_core.tools import tool
from ..chat.models import Change
from ..chat.ticket_fields import TicketFields
from .followup_models import FollowupPlan
from .followup import followups


def followup_tools(ctx: Any, internal: bool = False) -> list[Any]:
    @tool
    def read_ticket_followups() -> dict[str, Any]:
        """Reevaluate approved monitoring windows of this client. Returns missing data, persistence, review needed or closure candidate. Never closes tickets."""
        return ctx.record('read_ticket_followups',dict(observations=followups(ctx.client)))
    @tool
    def record_ticket_followup_review(ticket_id: str, expected_revision: str,
        conclusion: Literal['criterion_met','persists','needs_review'], summary: str,
        evidence_refs: list[str]) -> dict[str, Any]:
        """For specialist_review only: record a criterion-specific assessment after the full observation window. Requires current-turn real query evidence. Does not authorize or close tickets."""
        from .followup_review import record_followup_review
        return ctx.record('record_ticket_followup_review',record_followup_review(ctx,ticket_id,
            expected_revision,conclusion,summary,evidence_refs))
    @tool
    def propose_ticket_followup(ticket_id: str, expected_revision: str, followup: FollowupPlan,
                                tags: list[str] | None = None) -> dict[str, Any]:
        """Propose MONITORING on the SAME ticket with reason, event date, observation days and closure criterion. Window starts the day after the event. return_to_baseline checks anomaly daily costs; other topics use specialist_review. Reuses app approval; nothing is applied until the user approves."""
        from ..chat.ticket_proposals import propose
        ticket = ctx.ops.tickets([ticket_id])[0]
        if ticket['status'] not in ('PROPOSED','APPROVED','MONITORING','IMPLEMENTED','REJECTED','SNOOZED'):
            raise ValueError('Usa un ticket abierto; no reabras una decisión cerrada con esta herramienta.')
        fields = TicketFields(followup=followup,tags=list(dict.fromkeys([*ticket.get('tags',[]),*(tags or [])])))
        start,end = followup.window()
        note = f"{followup.reason}\nSeguimiento desde {start} hasta {end} (fin exclusivo). Criterio: {followup.closure_criterion}"
        return propose(ctx,[Change(ticket_id=ticket_id,expected_revision=expected_revision,
            target_status='MONITORING',fields=fields,append_note=note,reason=followup.reason,
            evidence_refs=['message:'+ctx.turn_id])])
    reads = [read_ticket_followups,record_ticket_followup_review]
    return reads if internal else [*reads,propose_ticket_followup]
