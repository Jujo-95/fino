"""Classify observations independently from ticket lifecycle decisions."""
from typing import Any
from ..models import Finding, FinOpsTicket, IncrementalPolicy

IDENTITY = ('capability', 'sub_account_id', 'service_name', 'kpi_name')
CLOSED = {'IMPLEMENTED', 'FALSE_POSITIVE', 'REJECTED', 'RESOLVED'}


def identity(finding: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(finding[key] for key in IDENTITY)


def prior_findings(baseline: dict[str, Any] | None) -> dict[tuple[Any, ...], dict[str, Any]]:
    if not baseline:
        return {}
    observations = baseline.get('incremental', {}).get('observations')
    if observations is None:
        traces = [event['payload'].get('trace') for event in baseline.get('events', [])]
        synthesis: dict[str, Any] = next((t for t in traces if t and t['node'] == 'synthesize'), {})
        observations = synthesis.get('findings', [])
    return {identity(item):item for item in observations}


def material_change(before: dict[str, Any], after: dict[str, Any], policy: IncrementalPolicy) -> bool:
    threshold = policy.metrics.get(after['kpi_name'], policy.default)
    if before['severity'] != after['severity']:
        return True
    for key in ('kpi_value', 'estimated_monthly_impact_usd'):
        old, new = before.get(key), after.get(key)
        if (old is None) != (new is None):
            return True
        if old is not None and new is not None:
            distance = abs(new-old)
            if distance > 0 and distance >= threshold.absolute and (old == 0 or distance/abs(old)*100 >= threshold.relative_pct):
                return True
    return False


def classify(before: dict[str, Any] | None, after: dict[str, Any], comparable: bool,
             status: str, policy: IncrementalPolicy) -> tuple[str, str]:
    if status in CLOSED or status == 'SNOOZED':
        return 'decision_preserved', 'Conservar la decisión humana; validar evidencia nueva antes de reabrir.'
    if before is None:
        return 'new', 'No consta en las observaciones del informe anterior.'
    if not comparable:
        return 'coverage_changed', 'Cambió el período; no comparar importes acumulados como variación real.'
    if material_change(before, after, policy):
        return 'updated', 'Cambió la severidad o una métrica superó el umbral de materialidad.'
    return 'persistent', 'Sin cambios materiales; se mantiene el seguimiento del ticket existente.'


def build_delta(state: dict[str, Any], tickets: list[FinOpsTicket], all_tickets: list[FinOpsTicket],
                policy: IncrementalPolicy) -> dict[str, Any]:
    baseline = state.get('baseline')
    before = prior_findings(baseline)
    comparable = not baseline or all(state[key] == baseline[key] for key in ('period_start_utc', 'period_end_utc'))
    changes = []
    for item, ticket in zip(state['findings'], tickets):
        previous = before.get(identity(item))
        kind, reason = classify(previous, item, comparable, ticket.status, policy)
        changes.append(dict(ticket_id=ticket.ticket_id, kind=kind, reason=reason,
            previous=previous, current=item, status=ticket.status,
            contributors=[c.model_dump() for c in ticket.contributors]))
    observed = {ticket.ticket_id for ticket in tickets}
    review = [review_ticket(ticket, ticket.ticket_id in observed, state, comparable) for ticket in all_tickets]
    novel = any(change['kind'] in ('new', 'updated') for change in changes)
    return dict(outcome='initial' if not baseline else 'changes' if novel else 'data_updated_no_new_actions',
        previous_run_id=baseline['run_id'] if baseline else None, comparable_period=comparable,
        prior_period={key:baseline[key] for key in ('period_start_utc','period_end_utc')} if baseline else None,
        changes=changes, observations=[Finding.model_validate(item).model_dump() for item in state['findings']],
        ticket_review=review, policy=policy.model_dump(), metric_changes=metric_changes(state, comparable, policy))


def review_ticket(ticket: FinOpsTicket, observed: bool, state: dict[str, Any], comparable: bool) -> dict[str, Any]:
    status = 'human_resolved' if ticket.status in CLOSED else 'observed_again' if observed else 'needs_validation'
    validation = check_condition(ticket, state, comparable) if status == 'needs_validation' else None
    if validation:
        status = 'condition_not_triggered'
    return dict(ticket_id=ticket.ticket_id, status=ticket.status, assessment=status,
        candidate_obsolete=bool(validation), validation=validation,
        resolution_note=ticket.resolution_note, last_updated_at_utc=ticket.updated_at_utc,
        reason='Decisión registrada por el usuario.' if status == 'human_resolved' else
               'Hallazgo observado en este análisis.' if observed else
               'La condición del indicador ya no se activa; validar el motivo antes de cambiar el estado.' if validation else
               'No observado en este análisis; esto no demuestra resolución ni falso positivo.',
        suggested_status=None, evidence_summary=ticket.evidence_summary,
        contributors=[c.model_dump() for c in ticket.contributors])


def metric_changes(state: dict[str, Any], comparable: bool, policy: IncrementalPolicy) -> list[dict[str, Any]]:
    if not comparable or not state.get('baseline'):
        return []
    traces = [event['payload'].get('trace') for event in state['baseline'].get('events', [])]
    old = {m['key']:m for t in traces if t and t['node'] == 'ingest_and_profile' for m in t.get('metrics', [])}
    return [dict(key=m['key'], label=m['label'], previous=old[m['key']]['value'], current=m['value'], unit=m['unit'])
            for m in state['kpi_snapshots']['metrics'] if m['key'] in old and material_change(
                dict(kpi_name=m['key'], kpi_value=old[m['key']]['value'], severity='LOW'),
                dict(kpi_name=m['key'], kpi_value=m['value'], severity='LOW'), policy)]


def check_condition(ticket: FinOpsTicket, state: dict[str, Any], comparable: bool) -> dict[str, Any] | None:
    keys = {'unallocated_cost_pct', 'anomaly_unpredicted_variance', 'commitment_discount_waste_pct'}
    overview = state['kpi_snapshots']
    if not comparable or ticket.kpi_name not in keys or overview.get('observed_days', 0) < 4:
        return None
    metric = next((m for m in overview['metrics'] if m['key'] == ticket.kpi_name), None)
    if not metric or metric['value'] != 0:
        return None
    return dict(source='script_snapshot', snapshot_id=overview.get('snapshot_id'), metric=ticket.kpi_name,
        value=0, query_refs=[q['query_id'] for q in overview.get('query_evidence', [])],
        limitation='Un indicador en cero no acredita implementación ni demuestra un falso positivo histórico.')
