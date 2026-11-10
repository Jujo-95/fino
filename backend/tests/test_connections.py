from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.engine.script_store import ScriptStore
from finops_agent.models import ClientProfile


def test_inventory_is_scoped_read_only_and_never_exposes_context_or_secrets(container,csv_path,monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY','private-api-key')
    client=container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    notes=client.workspace/'context_notes'
    notes.mkdir(exist_ok=True)
    (notes/'local.md').write_text('Confidential business context')
    other=container.onboard(ClientProfile(client_id='other',client_name='Other'))
    foreign=other.workspace/'context_notes'
    foreign.mkdir(exist_ok=True)
    (foreign/'foreign.md').write_text('Other client context')
    app.dependency_overrides[get_container]=lambda:container
    try:
        http=TestClient(app)
        for _ in range(2):
            response=http.get('/api/v1/clients/acme/connections')
            assert response.status_code==200
            data=response.json()
            assert data['client_id']=='acme' and len(data['imports'])==1
            assert [d['name'] for d in data['documents']]==['local.md']
            assert not data['external_mcp_supported']
            assert {'query_finance','plan_ticket_changes','list_reports'}<={t['name'] for t in data['tools']}
            assert all(value not in response.text for value in ['private-api-key','Confidential','foreign.md','Other client context'])
        assert not container.chat.tasks
        assert not (client.workspace/'chat/threads').exists()
    finally:
        app.dependency_overrides.clear()


def test_report_measurements_filter_before_pagination_and_are_client_scoped(container):
    first=ScriptStore(container.client('acme').engine)
    wanted=first.save({},'historical-report')
    for i in range(101):
        first.save({},'recent-'+str(i))
    other=container.onboard(ClientProfile(client_id='other',client_name='Other'))
    ScriptStore(other.engine).save({},'historical-report')
    assert wanted not in {r['snapshot_id'] for r in first.list()}
    app.dependency_overrides[get_container]=lambda:container
    try:
        http=TestClient(app)
        data=http.get('/api/v1/clients/acme/scripts?run_id=historical-report').json()
        assert len(data)==1 and data[0]['snapshot_id']==wanted
        assert first.list('not-a-report')==[]
    finally:
        app.dependency_overrides.clear()
