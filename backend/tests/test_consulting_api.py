from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container


@pytest.fixture
def http(container):
    app.dependency_overrides[get_container] = lambda: container
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_context_http_review_confirm_conflict_and_safe_defaults(http, container):
    base = '/api/v1/clients/acme/consulting'
    initial = http.get(base)
    assert initial.status_code==200
    d = initial.json()['diagnosis']
    response = http.post(base+'/context/proposals', json=dict(expected_revision=d['context']['revision'],
        values=dict(monthly_budget=25000), reason='Confirmado por Finanzas'))
    assert response.status_code==200
    key = response.json()['proposal_id']
    assert http.get(base).json()['diagnosis']['context']['values']=={}
    decision = dict(decision='confirm', command_id=uuid4().hex)
    path = base+'/context/proposals/'+key+'/decision'
    assert http.post(path,json=decision).json()==http.post(path,json=decision).json()
    assert http.get(base).json()['diagnosis']['context']['values']['monthly_budget']==25000
    assert http.get('/api/v1/clients/acme/overview').json()['budget']==25000
    stale = http.post(base+'/context/proposals',json=dict(expected_revision=d['context']['revision'],
        values=dict(objective='Control'), reason='Otro cambio'))
    assert stale.status_code==409
    tasks = container.client('acme').tickets.list()
    assert all(t.ticket_kind=='onboarding' for t in tasks)
    assert next(t for t in tasks if t.workflow_key=='requirement:monthly_budget').status=='IMPLEMENTED'


@pytest.mark.parametrize('values', [{'monthly_budget':-1}, {'arbitrary_sql':'DROP TABLE'}, {'expected_accounts':[]}])
def test_context_http_rejects_invalid_contract(http, values):
    base = '/api/v1/clients/acme/consulting'
    revision = http.get(base).json()['diagnosis']['context']['revision']
    assert http.post(base+'/context/proposals',json=dict(expected_revision=revision,
        values=values, reason='Test')).status_code==422
