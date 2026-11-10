import asyncio
import csv
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from finops_agent.engine.run_audit import RunAuditStore
from finops_agent.engine.report_delta import classify
from finops_agent.models import RunRequest, TicketUpdate, IncrementalPolicy, Finding
from finops_agent.agents.incremental import history_for_node

BODY = dict(client_id='acme', period_start_utc='2026-10-01', period_end_utc='2026-10-21')


def run(container, **updates):
    async def execute():
        from finops_agent.engine.report_guard import repeat_prompt
        prompt = repeat_prompt(container.client('acme'),BODY['period_start_utc'],BODY['period_end_utc'])
        consent = dict(repeat_confirmation=prompt['confirmation_id']) if prompt else {}
        record = container.jobs.start(RunRequest(**{**BODY, **updates, **consent}))
        await container.jobs.tasks[record['run_id']]
        return RunAuditStore(container.client('acme').workspace).read(record['run_id'])
    return asyncio.run(execute())


def counting_provider(container):
    provider = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='Explicit test double')))
    container.llm = provider
    return provider


def test_identical_run_skips_models_and_preserves_immutable_report(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    provider = counting_provider(container)
    first = run(container)
    assert first['status'] == 'completed'
    before = {ticket.ticket_id:ticket.model_dump() for ticket in client.tickets.list()}
    calls = provider.ainvoke.await_count
    second = run(container)
    assert second['status'] == 'completed'
    assert second['reused_run_id'] == first['run_id']
    assert second['report_markdown'] == ''
    assert second['incremental']['outcome'] == 'no_changes'
    assert provider.ainvoke.await_count == calls == 5
    assert len(RunAuditStore(client.workspace).reports()) == 1
    assert len(list((client.workspace/'reports').glob('*.md'))) == 1
    assert {t.ticket_id:t.model_dump() for t in client.tickets.list()} == before
    assert RunAuditStore(client.workspace).detail(second['run_id'])['report_markdown'] == first['report_markdown']


@pytest.mark.parametrize('change', ['note', 'decision', 'policy', 'correction', 'instruction', 'force'])
def test_changed_inputs_invalidate_reuse(container, csv_path, change):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    first = run(container)
    kwargs = {}
    if change == 'note':
        client.tickets.index_context('note:approval', 'An approved initiative starts tomorrow.')
    elif change == 'decision':
        ticket = client.tickets.list()[0]
        client.tickets.update(ticket.ticket_id, TicketUpdate(status='FALSE_POSITIVE', resolution_note='Approved by owner'))
    elif change == 'policy':
        container.onboard(client.profile.model_copy(update={'planned_monthly_cost':1234}))
    elif change == 'correction':
        correct_csv(client, csv_path)
    elif change == 'instruction':
        kwargs['instruction'] = 'Revisa la iniciativa aprobada.'
    else:
        kwargs.update(force_reanalysis=True, force_reason='Revisión solicitada por el analista')
    second = run(container, **kwargs)
    assert second['status'] == 'completed'
    assert not second.get('reused_run_id')
    assert second['reference_run_id'] == first['run_id']
    assert second['report_file'] != first['report_file']
    assert (client.workspace/'reports'/first['report_file']).read_text() == first['report_markdown']
    assert len(client.tickets.list()) == len(first['incremental']['ticket_review'])
    if change == 'decision':
        assert client.tickets.list()[0].status == 'FALSE_POSITIVE'
        assert second['incremental']['ticket_review'][0]['assessment'] == 'human_resolved'


def test_period_change_keeps_problem_identity_and_requires_revalidation(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    first = run(container)
    original = client.tickets.list()[0]
    renewed = client.tickets.create(Finding.model_validate(original.model_dump()).model_copy(update={'period_bucket':'2026-11'}))
    assert renewed.ticket_id == original.ticket_id
    second = run(container, period_end_utc='2026-10-20')
    assert not second['incremental']['comparable_period']
    assert any(item['kind'] == 'coverage_changed' for item in second['incremental']['changes'])
    absent = [item for item in second['incremental']['ticket_review'] if item['assessment'] == 'needs_validation']
    assert absent and all(item['suggested_status'] is None for item in absent)
    assert all(t.status == 'PROPOSED' for t in client.tickets.list())
    assert first['run_id'] == second['reference_run_id']


@pytest.mark.parametrize('value,severity,status,expected', [(100.01,'HIGH','PROPOSED','persistent'),
    (120,'HIGH','PROPOSED','updated'), (120,'HIGH','FALSE_POSITIVE','decision_preserved'),
    (100,'CRITICAL','PROPOSED','updated')])
def test_materiality_ignores_cosmetic_changes(value, severity, status, expected):
    before = dict(kpi_name='metric', kpi_value=100, severity='HIGH', title='Before', estimated_monthly_impact_usd=None)
    after = {**before, 'kpi_value':value, 'severity':severity, 'title':'Reworded'}
    assert classify(before, after, True, status, IncrementalPolicy())[0] == expected


def test_history_is_scoped_and_force_requires_reason():
    context = dict(tickets=[dict(capability='allocation'), dict(capability='budgeting')], contributions=[])
    assert history_for_node(dict(historical_context=context), 'allocation')['tickets'] == [dict(capability='allocation')]
    with pytest.raises(ValueError, match='requires a reason'):
        RunRequest(**BODY, force_reanalysis=True)


def test_failed_run_is_not_baseline_and_restart_keeps_reuse(container, csv_path):
    from finops_agent.api.container import AppContainer
    from finops_agent.config import KB_DIR
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    first = run(container)
    store = RunAuditStore(client.workspace)
    failed = store.create(RunRequest(**BODY).model_dump(), 'mock')
    store.finish(failed, 'failed', 'Explicit failure fixture')
    restarted = AppContainer(container.workspaces, KB_DIR)
    try:
        second = run(restarted)
        assert second['reused_run_id'] == first['run_id']
        assert second['reused_run_id'] != failed['run_id']
    finally:
        restarted.close()


def test_new_month_does_not_duplicate_known_problems(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    first = run(container)
    before = {t.ticket_id for t in client.tickets.list()}
    csv_path.write_text(csv_path.read_text().replace('2026-10-', '2026-11-'))
    client.engine.ingest_focus_csv('acme', csv_path)
    second = run(container, period_start_utc='2026-11-01', period_end_utc='2026-11-21')
    assert second['status'] == 'completed'
    assert second['reference_run_id'] == first['run_id']
    assert {t.ticket_id for t in client.tickets.list()} == before
    assert not second['incremental']['comparable_period']
    assert second['incremental']['metric_changes'] == []


def test_resolved_condition_is_a_candidate_not_an_automatic_transition(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    run(container)
    anomaly = next(t for t in client.tickets.list() if t.capability == 'anomaly-management')
    client.tickets.index_context('note:planned', '---\nplanned_events:\n  - sub_account_id: ml-platform\n'
        '    service_name: Vertex AI\n    start_utc: 2026-10-19\n    end_utc: 2026-10-22\n    approved: true\n---\nApproved training')
    second = run(container)
    review = next(t for t in second['incremental']['ticket_review'] if t['ticket_id'] == anomaly.ticket_id)
    assert review['candidate_obsolete']
    assert review['validation']['query_refs']
    assert review['suggested_status'] is None
    assert next(t for t in client.tickets.list() if t.ticket_id == anomaly.ticket_id).status == 'PROPOSED'


def correct_csv(client, csv_path):
    with csv_path.open() as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    rows[0]['EffectiveCost'] = str(float(rows[0]['EffectiveCost'])+500)
    with csv_path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    client.engine.ingest_focus_csv('acme', csv_path)
