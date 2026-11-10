import asyncio
from unittest.mock import patch
import pytest
from finops_agent.models import RunRequest
from finops_agent.engine.run_audit import RunAuditStore
from test_run_audit import BODY


class BlockingGraph:
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def astream(self, initial, stream_mode):
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        yield {'synthesize': {'report_markdown':'Persisted backend result', 'audit_traces':[]}}


@pytest.mark.asyncio
async def test_disconnect_and_reconnect_preserve_backend_job(container):
    graph = BlockingGraph()
    with patch('finops_agent.api.run_jobs.build_graph', return_value=graph):
        record = container.jobs.start(RunRequest(**BODY))
        await graph.entered.wait()
        subscription = container.jobs.subscribe('acme', record['run_id'])
        assert (await anext(subscription))['node'] == '__heartbeat__'
        await subscription.aclose()  # Refresh/close only disconnects this observer.
        assert not container.jobs.tasks[record['run_id']].done()
        assert container.jobs.start(RunRequest(**BODY))['run_id'] == record['run_id']
        graph.release.set()
        await container.jobs.tasks[record['run_id']]
        replay = [event async for event in container.jobs.subscribe('acme', record['run_id'])]
    assert graph.calls == 1
    assert [event['node'] for event in replay] == ['synthesize','__done__']
    saved = RunAuditStore(container.client('acme').workspace).read(record['run_id'])
    assert saved['status'] == 'completed'
    assert saved['report_markdown'] == 'Persisted backend result'


@pytest.mark.asyncio
async def test_http_start_returns_before_execution_finishes(container):
    import httpx
    from finops_agent.api.server import app
    from finops_agent.api.routes import get_container
    graph = BlockingGraph()
    app.dependency_overrides[get_container] = lambda: container
    try:
        with patch('finops_agent.api.run_jobs.build_graph', return_value=graph):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                response = await client.post('/api/v1/runs', json=BODY)
                run_id = response.json()['run_id']
                await graph.entered.wait()
                assert response.status_code == 200
                history = (await client.get('/api/v1/clients/acme/runs')).json()
                assert history[0]['status'] == 'running'
                graph.release.set()
                await container.jobs.tasks[run_id]
                result = await client.get(f'/api/v1/clients/acme/runs/{run_id}/events')
                assert '__done__' in result.text
    finally:
        app.dependency_overrides.clear()
        await container.jobs.shutdown()
