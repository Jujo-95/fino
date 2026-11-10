import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.engine.run_audit import RunAuditStore
from finops_agent.models import ClientProfile

BODY = dict(client_id='acme', run_mode='daily', period_start_utc='2026-10-01',
            period_end_utc='2026-10-21', billing_currency='USD')


def execute(container, csv_path):
    container.client('acme').engine.ingest_focus_csv('acme', csv_path)
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post('/api/v1/runs/stream', json=BODY)
            frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
            run_id = frames[0]['run_id']
            history = client.get('/api/v1/clients/acme/runs').json()
            record = client.get('/api/v1/clients/acme/runs/' + run_id).json()
        return frames, history, record
    finally:
        app.dependency_overrides.clear()


def test_recorded_queries_and_individual_contributions(container, csv_path):
    container.client('acme').tickets.index_context('note:audit-fixture', 'ml-platform Vertex AI unplanned usage requires review.')
    frames, history, record = execute(container, csv_path)
    assert frames[-1]['node'] == '__done__'
    assert record['status'] == 'completed'
    assert history[0]['run_id'] == record['run_id']
    assert len(record['queries']) == 3
    assert record['queries'][0]['parameters']['client_id'] == 'acme'
    assert record['queries'][0]['sample_rows'][0]['actual'] == 49110
    traces = {event['node']: event['payload']['trace'] for event in record['events']}
    counts = [len(traces[name]['findings']) for name in ('allocation','anomaly','forecasting','budgeting','commitment')]
    assert sum(counts) == len(traces['synthesize']['findings'])
    assert traces['forecasting']['findings'] == []
    assert all(traces[name]['queries'] == [] for name in ('allocation','anomaly','forecasting','budgeting','commitment'))
    assert traces['anomaly']['query_refs'] == [record['queries'][2]['query_id']]
    assert traces['anomaly']['context']
    assert traces['allocation']['prompt'] is None
    assert 'Aportes por especialista' in record['report_markdown']
    assert 'Proyecciones — 0 hallazgo(s)' in record['report_markdown']
    store = RunAuditStore(container.client('acme').workspace)
    assert {**store.read(record['run_id']),'ticket_ids':[]} == record


def test_failed_model_keeps_partial_audit(container, csv_path):
    container.llm = SimpleNamespace(ainvoke=AsyncMock(side_effect=RuntimeError('model unavailable')))
    frames, _, record = execute(container, csv_path)
    assert frames[-1]['node'] == '__error__'
    assert record['status'] == 'failed'
    assert record['failed_node'] == 'allocation'
    assert record['error'] == 'model unavailable'
    assert len(record['queries']) == 3
    assert len(record['events']) == 1
    assert record['report_markdown'] == ''
    assert container.client('acme').tickets.list() == []


def test_tenant_cannot_read_another_execution(container, csv_path):
    _, _, record = execute(container, csv_path)
    container.onboard(ClientProfile(client_id='other',client_name='Other'))
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/clients/other/runs/' + record['run_id']).status_code == 404
            assert client.get('/api/v1/clients/other/runs').json() == []
            assert client.get('/api/v1/clients/acme/runs/bad-run-id').status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_prompt_and_final_response_are_audited(container, csv_path):
    container.llm = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(
        content='Final commentary with evidence.', reasoning_content='private internal reasoning')))
    _, _, record = execute(container, csv_path)
    traces = [event['payload']['trace'] for event in record['events']]
    allocation = next(trace for trace in traces if trace['node'] == 'allocation')
    assert allocation['engine'] == 'rules_with_llm_commentary'
    assert allocation['prompt']['messages'][0]['role'] == 'system'
    assert allocation['llm_output'] == 'Final commentary with evidence.'
    assert allocation['context']
    assert 'private internal reasoning' not in json.dumps(record)
    assert container.llm.ainvoke.await_count == 5
