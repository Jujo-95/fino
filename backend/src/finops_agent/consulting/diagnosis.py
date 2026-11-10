from typing import Any
from datetime import datetime, timezone
from ..agents.audit_trace import timestamp
from ..engine.incremental_inputs import digest
from .store import ConsultingStore
from .facts import billing_facts
from .availability import use_case_availability
from .supporting import supporting_data, supporting_quality

TITLES = {'data': 'Fiabilidad de los datos', 'allocation': 'Responsabilidad del gasto',
          'budget': 'Presupuesto', 'anomaly': 'Anomalías', 'usage': 'Uso de recursos',
          'rate': 'Tarifas y compromisos', 'operate': 'Resultados de tus cambios'}


def requirement(key: str, capability: str, question: str, reason: str) -> dict[str, Any]:
    return dict(id=key, capability=capability, question=question, reason=reason, status='missing')


def evaluate(client: Any) -> dict[str, Any]:
    store = ConsultingStore(client)
    context = store.context()
    facts = billing_facts(client, context['values'])
    supporting = supporting_data(client)
    supporting.update(supporting_quality(client, facts, context['values'].get('minimum_history_days', 7)))
    facts.update(supporting=supporting, fingerprint=digest([facts['fingerprint'], supporting]))
    tickets = [t.model_dump(mode='json') for t in client.tickets.list()]
    reviews = store.all('specialist_assessment')
    basis = digest([facts['fingerprint'],context['revision'],facts['stale'],datetime.now(timezone.utc).date()])
    key = digest([facts['fingerprint'], context['revision'], tickets, facts['stale'],
                  datetime.now(timezone.utc).date(), reviews, 'consulting-v1'])
    cached = store.get('assessment', key)
    if cached:
        return cached
    capabilities, requirements = assess(facts, context['values'], tickets)
    apply_reviews(capabilities,reviews,basis)
    record = dict(client_id=client.profile.client_id, revision=key, evaluated_at=timestamp(),
        evidence_id='assessment:'+key,
        data_through=facts['data_through'], period=dict(start=facts['available_from'], end=facts['data_through']),
        evidence_refs=['billing:'+facts['fingerprint']], facts=facts, capabilities=capabilities,
        requirements=requirements, context=context, pending_proposals=[], rule_version='consulting-v1',
        use_case_preflight=use_case_availability(client), basis_revision=basis)
    with client.engine.atomic_tx() as tx:
        store.put(tx, 'assessment', key, record)
    return record


def assess(facts: dict[str, Any], values: dict[str, Any], tickets: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    reqs = prerequisites(facts, values)
    active = [t for t in tickets if t.get('ticket_kind', 'finding') == 'finding' and t['status'] in ('PROPOSED', 'APPROVED', 'MONITORING')]
    capabilities = []
    mapping = {'data': 'data-ingestion', 'allocation': 'allocation', 'budget': 'budgeting',
               'anomaly': 'anomaly-management', 'usage': 'usage-optimization', 'rate': 'rate-optimization'}
    for key, title in TITLES.items():
        missing = [r['id'] for r in reqs if r['capability'] == key]
        related = [t['ticket_id'] for t in active if t['capability'] == mapping.get(key)]
        state = 'INSUFFICIENT_DATA' if missing or not facts['row_count'] else 'ASSESSABLE'
        if related:
            state = 'ATTENTION_REQUIRED'
        if key == 'operate':
            state = 'FOLLOW_UP' if any(t['status']=='IMPLEMENTED' and t.get('ticket_kind', 'finding')=='finding' for t in tickets) else 'INSUFFICIENT_DATA'
        capabilities.append(dict(key=key, title=title, state=state, missing_requirements=missing,
            ticket_ids=related, reason=explanation(key, state, facts), phase='Inform' if key in ('data','allocation','budget','anomaly') else 'Operate' if key=='operate' else 'Optimize'))
    return capabilities, reqs


def prerequisites(f: dict[str, Any], v: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    def add(condition: bool, key: str, capability: str, question: str, reason: str) -> None:
        if condition:
            rows.append(requirement(key, capability, question, reason))
    add(not f['row_count'], 'billing', 'data', 'Importa tus datos de facturación', 'Sin costes no podemos evaluar el gasto.')
    add(not v.get('expected_accounts'), 'expected_accounts', 'data', '¿Qué cuentas o proyectos deben estar incluidos?', 'Confirmamos el alcance antes de afirmar que los costes están completos.')
    add(not f['freshness_known'], 'cadence', 'data', '¿Cada cuántos días llegan los datos y con qué retraso?', 'Necesitamos distinguir una fuente retrasada de su cadencia habitual.')
    add(bool(f['missing_accounts']), 'missing_accounts', 'data', 'Faltan cuentas confirmadas: '+', '.join(f['missing_accounts']), 'Revisa el alcance de la exportación.')
    add(f['stale'], 'stale', 'data', 'Actualiza los costes recibidos', 'La fuente supera la cadencia y latencia confirmadas.')
    add(bool(f['missing_days']), 'gaps', 'data', 'Revisa los días sin cargos', 'Pueden ser días sin uso o particiones faltantes; hay que confirmarlo.')
    add(True, 'invoice', 'data', 'Pendiente de conciliación con factura', 'La validación interna no demuestra conciliación ni conformidad FOCUS completa.')
    add(any(not v.get('owners', {}).get(a) for a in f['accounts']), 'owners', 'allocation', '¿Quién responde por el gasto de cada cuenta?', 'Una etiqueta presente no confirma un responsable.')
    add(not v.get('monthly_budget'), 'monthly_budget', 'budget', '¿Cuál es tu presupuesto mensual aprobado?', 'El presupuesto heredado o sugerido no se considera aprobado.')
    add(f['observed_days'] < v.get('minimum_history_days', 7), 'history', 'anomaly', 'Necesitamos más días para comparar cambios', 'El histórico mínimo es una política ajustable, no un mandato de FOCUS.')
    add(not v.get('objective'), 'objective', 'budget', '¿Qué quieres mejorar primero?', 'Podemos priorizar control, visibilidad o reducción de coste.')
    add(not f['supporting']['utilization_ready'], 'utilization', 'usage', 'Faltan métricas de utilización suficientes del alcance', 'Los costes permiten investigar; no prueban que un recurso pueda reducirse sin riesgo.')
    add(not f['supporting']['matched_active_terms'], 'contracts', 'rate', 'Faltan términos y vencimientos de compromisos vigentes', 'Los cargos permiten investigar desperdicio; no justifican una nueva compra.')
    return rows


def explanation(key: str, state: str, facts: dict[str, Any]) -> str:
    if key == 'data':
        return 'Comprobaciones internas; conciliación y validación FOCUS formal pendientes.'
    if key == 'allocation':
        return 'Cobertura por coste positivo; responsables confirmados y etiquetas se evalúan por separado.'
    if key == 'rate' and facts['commitment_rows'] and not facts['supporting']['matched_active_terms']:
        return 'Hay cargos de compromisos para investigar, pero faltan términos para recomendar compras.'
    if key == 'operate':
        return 'Un cambio declarado requiere observación posterior; generar informes no verifica resultados.'
    return 'Hay acciones que requieren atención.' if state=='ATTENTION_REQUIRED' else 'Falta información para concluir.' if state=='INSUFFICIENT_DATA' else 'Datos disponibles para investigar; todavía no implica ausencia de problemas.'


def diagnosis(client: Any) -> dict[str, Any]:
    result = dict(evaluate(client))
    store = ConsultingStore(client)
    result['pending_proposals'] = [p for p in store.all('context_proposal') if p['status']=='pending']
    return result


def apply_reviews(capabilities: list[dict[str, Any]], reviews: list[dict[str, Any]], basis: str) -> None:
    for capability in capabilities:
        matches = sorted([r for r in reviews if r['capability']==capability['key']],key=lambda r:r['created_at'],reverse=True)
        if not matches:
            continue
        latest = matches[0]
        current = latest['basis_revision']==basis
        capability.update(last_review=dict(**{k:v for k,v in latest.items() if k!='queries'}, stale=not current))
        if current and not (latest['conclusion']=='NO_ISSUES_DETECTED' and
                            (capability['missing_requirements'] or capability['ticket_ids'])):
            capability.update(state=latest['conclusion'],reason=latest['summary'], evaluated_period=latest['period'])
