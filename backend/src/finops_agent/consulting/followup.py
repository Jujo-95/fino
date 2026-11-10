"""Deterministic observations; only an approved ticket operation changes lifecycle."""
from datetime import date, timedelta
from typing import Any
from ..engine.incremental_inputs import digest
from ..chat.operations import revision
from .store import ConsultingStore


def daily_rows(client: Any, ticket: Any, start: date, end: date) -> list[Any]:
    from ..sources.remote_config import read_remote
    if read_remote(client):
        from ..sources.result_cache import remote_result
        sql = "SELECT CAST(ChargePeriodStart AS DATE) AS day,sum(EffectiveCost) AS cost FROM focus_usage WHERE client_id=$client_id AND BillingCurrency=$currency AND ChargePeriodStart>=$start_utc AND ChargePeriodStart<$end_utc AND ($account='all' OR SubAccountId=$account) AND ($service='all' OR ServiceName=$service) GROUP BY 1 ORDER BY 1"
        result = remote_result(client,sql,dict(client_id=client.profile.client_id,currency=client.profile.billing_currency,
            start_utc=str(start),end_utc=str(end),account=ticket.sub_account_id,service=ticket.service_name),str(start),str(end))
        return [(date.fromisoformat(str(r['day'])[:10]),r['cost']) for r in result['rows']]
    with client.engine.lock:
        return list(client.engine.conn.execute(
            'SELECT CAST(ChargePeriodStart AS DATE), sum(EffectiveCost) FROM focus_usage '
            'WHERE client_id=? AND BillingCurrency=? AND ChargePeriodStart>=? AND ChargePeriodStart<? '
            "AND (?='all' OR SubAccountId=?) AND (?='all' OR ServiceName=?) GROUP BY 1 ORDER BY 1",
            [client.profile.client_id,client.profile.billing_currency,start,end,
             ticket.sub_account_id,ticket.sub_account_id,ticket.service_name,ticket.service_name]).fetchall())


def evaluate_followup(client: Any, ticket: Any) -> dict[str, Any]:
    with client.engine.lock:
        return _evaluate(client,ticket)


def observation_context(client: Any, ticket: Any, before: list[Any], after: list[Any], context: Any) -> dict[str, Any]:
    plan = ticket.followup
    start,end = plan.window()
    basis = digest([client.profile.client_id,revision(ticket),before,after,context['revision'],context.get('source_signature')])
    return dict(ticket_id=ticket.ticket_id,client_id=client.profile.client_id,
        ticket_revision=revision(ticket),basis_revision=basis,criterion=plan.closure_criterion,
        reason=plan.reason,check=plan.check,window_start=str(start),window_end_exclusive=str(end),
        observed_days=len(after),required_days=plan.observation_days,status='pending_data',
        scope=dict(account=ticket.sub_account_id,service=ticket.service_name),
        evidence_id='followup:'+basis,suggested_status=None,
        limitation='La comparación de coste no demuestra causalidad ni eficiencia operativa.')


def _evaluate(client: Any, ticket: Any) -> dict[str, Any]:
    plan = ticket.followup
    if plan is None:
        raise ValueError('El ticket no tiene un plan de seguimiento aprobado.')
    store = ConsultingStore(client)
    start,end = plan.window()
    before = daily_rows(client,ticket,plan.event_date-timedelta(days=plan.baseline_days),plan.event_date)
    after = daily_rows(client,ticket,start,end)
    context = store.context()
    context['source_signature'] = digest([client.engine.conn.execute(
        'SELECT file_hash FROM ingested_batches WHERE client_id=? ORDER BY file_hash',
        [client.profile.client_id]).fetchall(),store.all('utilization'),store.all('commitment')])
    result = observation_context(client,ticket,before,after,context)
    basis = result['basis_revision']
    latency = context['values'].get('data_latency_days')
    result['review_after'] = str(end+timedelta(days=latency or 0))
    if latency is None or date.today()<end+timedelta(days=latency) or len(after)!=plan.observation_days:
        result['summary'] = 'Faltan días completos o confirmar el retraso de los datos; no se puede proponer cierre.'
    elif plan.check=='return_to_baseline':
        result.update(cost_result(plan,before,after))
    else:
        result.update(status='needs_review',summary='Ventana disponible; el especialista debe comprobar el criterio aprobado.')
        assessment = store.get('ticket_followup_review',basis)
        if assessment:
            result.update(assessment)
    result['suggested_status'] = 'RESOLVED' if result['status']=='criterion_met' else None
    with client.engine.atomic_tx() as tx:
        store.put(tx,'ticket_followup_snapshot',basis,result)
    return result


def cost_result(plan: Any, before: list[Any], after: list[Any]) -> dict[str, Any]:
    if len(before)!=plan.baseline_days:
        return dict(status='needs_review',summary='Falta histórico previo completo; no se presume normalización.')
    baseline = sum(float(row[1]) for row in before)/len(before)
    if baseline<=0:
        return dict(status='needs_review',summary='La referencia previa no es positiva; requiere revisión especializada.')
    ceiling = baseline*(1+plan.tolerance_pct/100)
    met = all(0<=float(row[1])<=ceiling for row in after)
    return dict(status='criterion_met' if met else 'persists',baseline_daily_cost=baseline,
        allowed_daily_cost=ceiling,observed_daily_costs=[dict(day=str(day),cost=float(cost)) for day,cost in after],
        summary='Todos los días observados están dentro del límite acordado; se puede proponer cierre.' if met
        else 'El gasto aún supera el rango acordado o contiene ajustes negativos; continuar investigando.')


def followups(client: Any, refresh: bool = False) -> list[dict[str, Any]]:
    from ..sources.remote_config import read_remote
    if read_remote(client) and not refresh:
        from ..engine.analysis_store import latest_analysis
        value = latest_analysis(client)
        return list(value.get('followups',[])) if value else []
    with client.engine.lock:
        return [evaluate_followup(client,t) for t in client.tickets.list() if t.status in ('MONITORING','IMPLEMENTED')
                and t.ticket_kind=='finding' and t.followup]


def validate_followup_transition(client: Any, ticket: Any, change: Any) -> None:
    from .ticket_lifecycle import validate_defer
    validate_defer(ticket, change)
    incoming = change.fields.followup if change.fields and change.fields.followup else None
    plan = incoming or ticket.followup
    target = change.target_status or ticket.status
    if target == 'IMPLEMENTED' and ticket.ticket_kind == 'finding' and not plan:
        raise ValueError('Un ticket de optimización debe tener un plan de verificación antes de marcarse implementado.')
    if incoming and target!='MONITORING':
        raise ValueError('Aprueba el plan junto con el estado En seguimiento.')
    if target=='MONITORING' and ticket.status not in ('PROPOSED','APPROVED','MONITORING','IMPLEMENTED','REJECTED','SNOOZED'):
        raise ValueError('El seguimiento requiere un ticket abierto; conserva las decisiones cerradas.')
    if target=='MONITORING' and not plan:
        raise ValueError('En seguimiento requiere ventana, motivo y criterio de cierre.')
    if incoming and incoming.check=='return_to_baseline' and ticket.capability!='anomaly-management':
        raise ValueError('Volver al rango de coste solo verifica anomalías; usa revisión especializada para este tema.')
    if target=='FALSE_POSITIVE' and target!=ticket.status:
        text = (change.append_note+' '+change.reason).lower()
        if not change.evidence_refs or any(word in text for word in ('puntual','planeado','planificado','planned','one-off')):
            raise ValueError('Un evento puntual o planeado no es un hallazgo incorrecto. Usa seguimiento; para descartar aporta evidencia de que no aplicaba.')
    if target=='RESOLVED' and target!=ticket.status and ticket.ticket_kind=='finding':
        if not plan or ticket.status not in ('MONITORING','IMPLEMENTED'):
            raise ValueError('Primero registra el seguimiento y su criterio; cerrar requiere un resultado verificado.')
        if incoming:
            raise ValueError('No cambies el criterio en la misma propuesta que cierra el seguimiento.')
        if evaluate_followup(client,ticket)['status']!='criterion_met':
            raise ValueError('Falta evidencia actual que cumpla la ventana y el criterio de cierre.')
