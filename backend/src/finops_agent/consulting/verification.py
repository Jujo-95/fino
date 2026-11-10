from datetime import date, timedelta
from typing import Any
from ..agents.audit_trace import timestamp
from ..chat.operations import revision
from ..engine.incremental_inputs import digest
from .models import Implementation
from .store import ConsultingStore


def scope_rows(client: Any, ticket: Any, start: date, end: date) -> list[Any]:
    from ..sources.remote_config import read_remote
    if read_remote(client):
        from .followup import daily_rows
        return daily_rows(client,ticket,start,end)
    with client.engine.lock:
        return list(client.engine.conn.execute('SELECT CAST(ChargePeriodStart AS DATE), sum(EffectiveCost) '
            'FROM focus_usage WHERE client_id=? AND BillingCurrency=? AND ChargePeriodStart>=? '
            'AND ChargePeriodStart<? AND SubAccountId=? AND ServiceName=? GROUP BY 1 ORDER BY 1',
            [client.profile.client_id, client.profile.billing_currency, start, end,
             ticket.sub_account_id, ticket.service_name]).fetchall())


def register(client: Any, ticket_id: str, body: Implementation) -> dict[str, Any]:
    store = ConsultingStore(client)
    fingerprint = digest([ticket_id, body.model_dump(mode='json')])
    with client.engine.atomic_tx() as tx:
        receipt = store.get('implementation_command', body.command_id)
        if receipt:
            if receipt['fingerprint'] != fingerprint:
                raise ValueError('El comando ya pertenece a otra implementación.')
            return dict(receipt['result'])
        ticket = next((t for t in client.tickets.list() if t.ticket_id==ticket_id), None)
        if not ticket:
            raise KeyError('Ticket no encontrado en este cliente.')
        if ticket.ticket_kind != 'finding':
            raise ValueError('Solo una mejora implementada admite verificación de resultados.')
        if revision(ticket)!=body.expected_revision or ticket.status!='IMPLEMENTED':
            raise ValueError('Primero declara el ticket implementado y consulta su revisión actual.')
        if body.effective_date>date.today():
            raise ValueError('La fecha efectiva no puede ser futura.')
        baseline = scope_rows(client, ticket, body.effective_date-timedelta(days=body.baseline_days), body.effective_date)
        record = dict(verification_id=fingerprint, ticket_id=ticket_id, created_at=timestamp(),
            evidence_id='verification:'+fingerprint,
            client_id=client.profile.client_id, **body.model_dump(mode='json'),
            baseline=[dict(day=str(day), cost=float(cost)) for day,cost in baseline],
            status='pending_data', attributed_savings=None,
            scope=dict(account=ticket.sub_account_id, service=ticket.service_name),
            baseline_hash=digest(baseline),
            limitations='Comparación de facturación por cuenta/servicio. No demuestra causalidad ni rendimiento.')
        store.put(tx, 'verification', fingerprint, record)
        store.put(tx, 'implementation_command', body.command_id, dict(fingerprint=fingerprint, result=record))
        return record


def verifications(client: Any, refresh: bool = False) -> list[dict[str, Any]]:
    store = ConsultingStore(client)
    from ..sources.remote_config import read_remote
    if read_remote(client) and not refresh:
        return list(store.all('verification'))
    tickets = {t.ticket_id:t for t in client.tickets.list()}
    results = []
    for record in store.all('verification'):
        ticket = tickets.get(record['ticket_id'])
        if not ticket:
            continue
        result = observe(client, ticket, record, store.context()['values'])
        if result != record:
            with client.engine.atomic_tx() as tx:
                store.put(tx, 'verification', record['verification_id'], result)
        results.append(result)
    return results


def observe(client: Any, ticket: Any, record: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    start = date.fromisoformat(record['effective_date'])
    end = start+timedelta(days=record['observation_days'])
    after = scope_rows(client, ticket, start, end)
    baseline = record['baseline']
    latency = context.get('data_latency_days')
    ready = latency is not None and date.today() >= end+timedelta(days=latency)
    enough = len(after)==record['observation_days'] and len(baseline)==record['baseline_days']
    result = dict(record, after=[dict(day=str(day), cost=float(cost)) for day,cost in after])
    if not ready or len(after)<record['observation_days']:
        result.update(status='pending_data', reason='Esperando días completos y latencia confirmada; días sin cargos no se asumen como cero.')
    elif not enough:
        result.update(status='inconclusive', reason='Baseline incompleto: no se puede comparar con seguridad.')
    else:
        before_avg = sum(d['cost'] for d in baseline)/len(baseline)
        after_avg = sum(float(r[1]) for r in after)/len(after)
        difference = before_avg-after_avg
        result.update(status='observed' if difference>0 else 'no_improvement',
            before_daily_cost=before_avg, after_daily_cost=after_avg, observed_daily_reduction=difference,
            reason='Reducción observada; atribución pendiente de validar demanda y efecto operativo.' if difference>0 else 'No se observó reducción en esta ventana.')
    result['revision'] = digest({k:v for k,v in result.items() if k!='revision'})
    return result
