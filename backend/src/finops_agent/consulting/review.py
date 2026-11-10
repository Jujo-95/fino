from typing import Any
from ..agents.audit_trace import timestamp
from ..engine.incremental_inputs import digest
from .store import ConsultingStore
from .diagnosis import diagnosis


def record_review(ctx: Any, capability: str, conclusion: str, summary: str, evidence_refs: list[str]) -> dict[str, Any]:
    report = diagnosis(ctx.client)
    selected = next((c for c in report['capabilities'] if c['key']==capability), None)
    if not summary.strip() or len(summary)>2000 or not 1<=len(evidence_refs)<=20:
        raise ValueError('Usa un resumen concreto y entre una y veinte referencias de evidencia.')
    if selected is None or conclusion not in ('NO_ISSUES_DETECTED','ATTENTION_REQUIRED','FOLLOW_UP'):
        raise ValueError('Selecciona una capacidad y una conclusión soportadas.')
    thread = ctx.store.read(ctx.thread_id)
    queries = [a['result'] for a in thread['activity'] if a['turn_id']==ctx.turn_id
               and a['tool'] in ('query_finance','execute_use_case') and isinstance(a['result'],dict)
               and a['result'].get('evidence_id') in evidence_refs and not a['result'].get('truncated')
               and a['result'].get('rowCount',0)>0]
    if not queries or any(q.get('client_id')!=ctx.client.profile.client_id for q in queries):
        raise ValueError('La conclusión necesita una consulta real, no truncada, de este cliente y turno.')
    if conclusion=='NO_ISSUES_DETECTED' and (selected['missing_requirements'] or selected['ticket_ids']):
        raise ValueError('No se puede declarar ausencia de problemas con requisitos o tickets pendientes.')
    if conclusion=='NO_ISSUES_DETECTED' and (report['facts']['stale'] or not report['facts']['freshness_known']):
        raise ValueError('Confirma la cadencia y actualiza los datos antes de declarar ausencia de problemas.')
    periods = {(q['period_start_utc'],q['period_end_utc']) for q in queries}
    if len(periods)!=1:
        raise ValueError('Define una sola ventana evaluada; las comparaciones pueden leerse como evidencia adicional.')
    start,end = next(iter(periods))
    result = dict(client_id=ctx.client.profile.client_id, capability=capability, conclusion=conclusion,
        summary=summary, evidence_refs=[q['evidence_id'] for q in queries], queries=queries,
        period=dict(start=start,end=end), created_at=timestamp(), thread_id=ctx.thread_id,
        basis_revision=report['basis_revision'])
    key = digest([ctx.thread_id,ctx.turn_id,capability,conclusion,summary,evidence_refs])
    store = ConsultingStore(ctx.client)
    with ctx.client.engine.atomic_tx() as tx:
        result = store.get('specialist_assessment',key) or result
        store.put(tx,'specialist_assessment',key,result)
    return dict(evidence_id='review:'+key, **{k:v for k,v in result.items() if k!='queries'})
