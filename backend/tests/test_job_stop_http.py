import asyncio
import httpx
import pytest
from finops_agent.api.server import app
from finops_agent.api.routes import get_container
from finops_agent.models import RunRequest, ClientProfile


@pytest.mark.asyncio
async def test_report_stop_endpoint_cancels_existing_job_and_is_idempotent(container, monkeypatch):
    started = asyncio.Event()

    class Graph:
        async def astream(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()
            yield {}

    monkeypatch.setattr("finops_agent.api.run_jobs.build_graph", lambda c: Graph())
    request = RunRequest(
        client_id="acme",
        run_mode="daily",
        billing_currency="USD",
        period_start_utc="2026-10-01",
        period_end_utc="2026-10-21",
    )
    record = container.jobs.start(request)
    await asyncio.wait_for(started.wait(), 5)
    container.onboard(ClientProfile(client_id="other", client_name="Other"))
    app.dependency_overrides[get_container] = lambda: container
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            key = record["run_id"]
            assert (await client.post(f"/api/v1/clients/other/runs/{key}/stop")).status_code == 404
            response = await client.post(f"/api/v1/clients/acme/runs/{key}/stop")
            assert response.status_code == 200 and response.json()["status"] == "cancelled"
            assert response.json()["error"] == "Detenido por el usuario."
            assert (await client.post(f"/api/v1/clients/acme/runs/{key}/stop")).json()["status"] == "cancelled"
            events = [event async for event in container.jobs.subscribe("acme", key)]
            assert events[-1]["node"] == "__error__"
            assert not container.jobs.tasks
    finally:
        app.dependency_overrides.clear()
