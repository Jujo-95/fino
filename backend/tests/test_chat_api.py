import json
from uuid import uuid4
from fastapi.testclient import TestClient
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.models import ClientProfile
from test_chat_graph import ModelDouble
from test_chat_operations import ops as operations_fixture


def test_http_chat_tools_approval_and_tenant_scope(container):
    ops = operations_fixture.__wrapped__(container)
    container.llm = ModelDouble()
    container.onboard(ClientProfile(client_id='other',client_name='Other'))
    app.dependency_overrides[get_container] = lambda:container
    try:
        with TestClient(app) as client:
            base = '/api/v1/clients/acme/chat/threads'
            thread = client.post(base).json()
            url = base+'/'+thread['thread_id']
            assert container.llm.calls == 0  # Opening a conversation never calls the model.
            assert client.get('/api/v1/clients/other/chat/threads/'+thread['thread_id']).status_code == 404
            body = dict(text='Revisa FIN-001',ticket_refs=['FIN-001'],message_id=uuid4().hex)
            assert client.post(url+'/messages',json=body).status_code == 200
            stream = client.get(url+'/events')
            frames = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith('data: ')]
            assert frames[-1]['status']=='waiting'
            waiting = client.get(url).json()
            assert client.post(url+'/resume',json=dict(decision='approve',plan_ids=['forged'],message_id=uuid4().hex)).status_code == 422
            assert ops.tickets(['FIN-001'])[0]['status']=='PROPOSED'
            plan_id = waiting['pending'][0]['plan_id']
            assert client.post(url+'/resume',json=dict(decision='approve',plan_ids=[plan_id],message_id=uuid4().hex)).status_code == 200
            client.get(url+'/events')
            assert client.get(url).json()['status']=='ready'
            assert client.get(url+'/operations').json()[0]['result']['status']=='applied'
            assert client.get('/api/v1/clients/acme/tickets').json()[0]['status']=='APPROVED'
    finally:
        app.dependency_overrides.clear()
