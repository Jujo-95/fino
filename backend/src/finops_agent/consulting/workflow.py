"""Native, tenant-scoped tasks. Missing inputs never become fabricated findings."""
from typing import Any
from ..models import Finding, TicketUpdate
from ..engine.run_audit import RunAuditStore
from .diagnosis import diagnosis
from .models import ActionDetails

CAPABILITIES = {'data': 'data-ingestion', 'allocation': 'allocation', 'budget': 'budgeting',
                'anomaly': 'anomaly-management', 'usage': 'usage-optimization', 'rate': 'rate-optimization'}
TITLES = {'expected_accounts': 'Confirmar las cuentas que vamos a analizar',
          'cadence': 'Confirmar cuándo llegan los datos', 'owners': 'Asignar responsables al gasto',
          'monthly_budget': 'Confirmar el presupuesto mensual', 'objective': 'Definir qué queremos mejorar',
          'invoice': 'Conciliar los costes con la factura', 'utilization': 'Aportar datos de uso de los recursos',
          'contracts': 'Aportar las condiciones de los compromisos'}
REVIEWS = [('allocation', 'allocation', 'Revisar a quién se asigna el gasto'),
           ('anomaly', 'anomaly-management', 'Investigar los cambios de consumo'),
           ('budget', 'budgeting', 'Revisar el gasto frente al presupuesto'),
           ('forecast', 'forecasting', 'Revisar la proyección del gasto')]


def task(key: str, title: str, capability: str, reason: str, period: str,
         dependencies: list[str] | None = None, kind: str = 'onboarding') -> Finding:
    return Finding.model_validate(dict(ticket_kind=kind, workflow_key=key, capability=capability,
        maturity_tier='Crawl', allocation_mode='N/A', severity='MEDIUM', sub_account_id='all',
        service_name='all', period_bucket=period, kpi_name=key, kpi_value=None,
        estimated_monthly_impact_usd=None, title=title, evidence_summary=reason,
        recommended_action=reason, capability_citation_url='https://www.finops.org/framework/capabilities/'+capability+'/',
        action_details=ActionDetails(action_type='information' if kind=='onboarding' else 'investigation',
            steps=[title, 'Revisar la evidencia con el especialista y confirmar la conclusión.'],
            dependencies=dependencies or [], completion_criterion=(
                'Dato confirmado por el usuario o disponibilidad comprobada en la fuente.' if kind=='onboarding' else
                'Conclusión registrada para el período con evidencia verificable.'))))


def ensure(client: Any, finding: Finding, existing: dict[str, Any]) -> Any:
    key = finding.workflow_key
    assert key is not None
    if key not in existing:
        existing[key] = client.tickets.create(finding)
    return existing[key]


def sync_tasks(client: Any) -> dict[str, Any]:
    with client.engine.lock:
        report = diagnosis(client)
        existing = {t.workflow_key: t for t in client.tickets.list() if t.workflow_key}
        missing = {r['id'] for r in report['requirements']}
        for requirement in report['requirements']:
            key = requirement['id']
            ensure(client, task('requirement:'+key, TITLES.get(key, requirement['question']),
                CAPABILITIES[requirement['capability']], requirement['reason'], 'onboarding'), existing)
        for key, ticket in list(existing.items()):
            if key.startswith('requirement:') and key[12:] not in missing:
                complete(client, ticket, 'El dato requerido ya está confirmado o disponible en la fuente.')
        if report['data_through']:
            sync_reviews(client, report, existing)
        sync_followups(client, existing)
        return report


def complete(client: Any, ticket: Any, reason: str) -> None:
    if ticket.status in ('PROPOSED', 'APPROVED'):
        client.tickets.update(ticket.ticket_id, TicketUpdate(status='IMPLEMENTED',
            resolution_note='Comprobación automática: '+reason+' No representa ahorro verificado.'))


def sync_reviews(client: Any, report: dict[str, Any], existing: dict[str, Any]) -> None:
    through = report['data_through']
    period = through[:7]+'-01:'+through
    completed = any(r['status']=='completed' and r['client_id']==client.profile.client_id
        and r['period_start_utc'][:10]<=through[:7]+'-01' and r['period_end_utc'][:10]>through
        for r in RunAuditStore(client.workspace).list(limit=None))
    capabilities = {c['key']: c for c in report['capabilities']}
    for key, capability, title in REVIEWS:
        blockers = [t.ticket_id for t in existing.values() if t.workflow_key in
            ('requirement:billing', 'requirement:expected_accounts',
             *(['requirement:monthly_budget'] if key=='budget' else []),
             *(['requirement:history'] if key=='anomaly' else []))]
        item = ensure(client, task('review:'+key+':'+period, title, capability,
            'Revisar los indicadores del período y registrar una conclusión con evidencia; no implica un problema detectado.',
            period, blockers, 'analysis'), existing)
        review = capabilities.get(key, {}).get('last_review', {})
        if (review and not review['stale']) or (key=='forecast' and completed):
            complete(client, item, 'Hay una conclusión registrada para el período disponible.')
    report_task = ensure(client, task('report:'+period, 'Actualizar el análisis del período disponible',
        'reporting-analytics', 'Actualizar indicadores y hallazgos. La narración del informe es opcional.',
        period, kind='analysis'), existing)
    if completed:
        complete(client, report_task, 'Ya existe un informe guardado que cubre el período.')


def sync_followups(client: Any, existing: dict[str, Any]) -> None:
    from .verification import verifications
    observations = {v['ticket_id']: v for v in verifications(client)}
    for source in client.tickets.list():
        if source.ticket_kind!='finding' or source.status!='IMPLEMENTED':
            continue
        item = ensure(client, task('verification:'+source.ticket_id,
            'Verificar el resultado de '+source.ticket_id, source.capability,
            'Registrar cuándo se aplicó el cambio y comparar datos posteriores; implementado no significa ahorro demostrado.',
            source.period_bucket, kind='verification'), existing)
        result = observations.get(source.ticket_id)
        if result and result['status'] in ('observed', 'no_improvement'):
            complete(client, item, 'La comparación posterior está disponible: '+result['status'])
