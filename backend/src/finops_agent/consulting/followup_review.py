from typing import Any
from ..engine.incremental_inputs import digest
from .followup import evaluate_followup
from .store import ConsultingStore


def record_followup_review(ctx: Any, ticket_id: str, expected_revision: str, conclusion: str,
                           summary: str, evidence_refs: list[str]) -> dict[str, Any]:
    from ..models import FinOpsTicket
    ticket = FinOpsTicket.model_validate(ctx.ops.tickets([ticket_id])[0])
    result = evaluate_followup(ctx.client,ticket)
    if result['ticket_revision']!=expected_revision or ticket.status not in ('MONITORING','IMPLEMENTED'):
        raise ValueError('Consulta la revisión actual de un ticket en seguimiento.')
    if ticket.followup is None or ticket.followup.check!='specialist_review' or result['status']=='pending_data':
        raise ValueError('La revisión requiere el criterio especializado y su ventana de datos completa.')
    if conclusion not in ('criterion_met','persists','needs_review') or not 10<=len(summary.strip())<=2000:
        raise ValueError('Indica una conclusión y un resumen con alcance y limitaciones.')
    thread = ctx.store.read(ctx.thread_id)
    queries = [a['result'] for a in thread['activity'] if a['turn_id']==ctx.turn_id
        and a['tool'] in ('query_finance','execute_use_case') and isinstance(a['result'],dict)
        and a['result'].get('evidence_id') in evidence_refs and not a['result'].get('truncated')
        and a['result'].get('rowCount',0)>0]
    if not queries or any(q.get('client_id')!=ctx.client.profile.client_id for q in queries):
        raise ValueError('Usa consultas reales, no truncadas, de este cliente y turno.')
    if not any(q.get('period_start_utc','')[:10]<=result['window_start'] and
               q.get('period_end_utc','')[:10]>=result['window_end_exclusive'] for q in queries):
        raise ValueError('La consulta debe cubrir la ventana completa aprobada.')
    refs = [q['evidence_id'] for q in queries]
    assessment = dict(status=conclusion, summary=summary, review_evidence_refs=refs,
        reviewer=thread.get('agent_id'),review_thread_id=ctx.thread_id,
        limitation='Conclusión del especialista basada en evidencia; requiere aprobación del usuario para cerrar.')
    store = ConsultingStore(ctx.client)
    with ctx.client.engine.atomic_tx() as tx:
        store.put(tx,'ticket_followup_review',result['basis_revision'],assessment)
    return dict(evidence_id='followup-review:'+digest([result['basis_revision'],assessment]), **assessment)
