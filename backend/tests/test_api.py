import json
import pytest
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container


@pytest.fixture
def api_client(container):
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


def test_upload_sse_feedback_and_reports(api_client, csv_path):
    with csv_path.open('rb') as stream:
        response = api_client.post('/api/v1/clients/acme/uploads', files={'files': ('focus.csv', stream, 'text/csv')})
    assert response.status_code == 200
    assert response.json()['ingested_rows'] == 60
    assert api_client.get('/api/v1/health').json()['duckdb']
    response = api_client.post('/api/v1/runs/stream', json=dict(client_id='acme', run_mode='daily',
        period_start_utc='2026-10-01', period_end_utc='2026-10-21', billing_currency='USD'))
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert [event['node'] for event in frames] == ['ingest_and_profile','allocation','anomaly',
        'forecasting','budgeting','commitment','synthesize','__done__']
    tickets = api_client.get('/api/v1/clients/acme/tickets').json()
    anomaly = next(ticket for ticket in tickets if ticket['capability'] == 'anomaly-management')
    patch = api_client.patch('/api/v1/clients/acme/tickets/' + anomaly['ticket_id'],
        json={'status':'FALSE_POSITIVE','resolution_note':'Approved planned training'})
    assert patch.status_code == 200
    assert api_client.get('/api/v1/clients/acme/overview').json()['spikes'] == []
    assert api_client.get('/api/v1/clients/acme/reports').json()[0]['markdown'].startswith('# FinOps')


@pytest.mark.parametrize('start,end', [('2026-10-20','2026-10-01'),('2026-10-01','2026-12-01'),
    ('2026-10-01T00:00:00-05:00','2026-10-21T00:00:00-05:00'),('2026-10-02','2026-10-21')])
def test_bad_period(api_client, start, end):
    response = api_client.post('/api/v1/runs/stream', json=dict(client_id='acme',
        period_start_utc=start, period_end_utc=end))
    assert response.status_code == 422


def test_tenant_isolation_and_invalid_state(api_client):
    assert api_client.get('/api/v1/clients/does-not-exist/tickets').status_code == 404
    assert api_client.get('/api/v1/clients/..%2F../tickets').status_code != 200
    assert api_client.post('/api/v1/clients/onboard',json={'client_id':'../escape','client_name':'Escape'}).status_code == 422
    assert api_client.post('/api/v1/clients/onboard',json={'client_id':'euro','client_name':'Euro','billing_currency':'EUR'}).status_code == 422
    assert api_client.patch('/api/v1/clients/acme/tickets/FIN-001',json={'status':'BOGUS','resolution_note':'x'}).status_code == 422


def test_concurrent_dashboard_reads(container, csv_path):
    from concurrent.futures import ThreadPoolExecutor
    resource = container.client('acme')
    resource.engine.ingest_focus_csv('acme', csv_path)
    def read(index):
        if index % 2:
            return resource.tickets.list()
        return container.overview('acme')['actual']
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(read, range(80)))
    assert all(value == 49110 for value in values[::2])
