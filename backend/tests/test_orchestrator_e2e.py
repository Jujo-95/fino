import pytest
from finops_agent.agents.orchestrator import build_graph
from finops_agent.agents.specs import SPECIALIST_SPECS
from finops_agent.agents.runner import SpecialistRunner
from finops_agent.models import TicketUpdate


@pytest.mark.parametrize("name", list(SPECIALIST_SPECS))
async def test_specialists(name, container, csv_path):
    container.client("acme").engine.ingest_focus_csv("acme", csv_path)
    state = {"client_id": "acme", "kpi_snapshots": container.overview("acme"), "findings": []}
    result = await SpecialistRunner(SPECIALIST_SPECS[name], container)(state)
    assert "findings" in result
    assert all(f["capability_citation_url"].startswith("https://www.finops.org/") for f in result["findings"])


async def test_onboarding_daily_feedback(container, csv_path):
    client = container.client("acme")
    client.engine.ingest_focus_csv("acme", csv_path)
    graph = build_graph(container)
    state = dict(client_id="acme", run_mode="onboarding", period_start_utc="2026-10-01",
                 period_end_utc="2026-10-21", billing_currency="USD")
    first = await graph.ainvoke(state)
    anomaly = next(t for t in client.tickets.list() if t.capability == "anomaly-management")
    client.tickets.update(anomaly.ticket_id, TicketUpdate(status="FALSE_POSITIVE", resolution_note="Approved temporary training job"))
    second = await graph.ainvoke({**state, "run_mode": "daily"})
    assert second["active_anomalies"] == []
    assert second["excluded_baseload"] == ["ml-platform:Vertex AI"]
    assert not any(f["capability"] == "anomaly-management" for f in second["findings"])
    assert second["kpi_snapshots"]["forecast"] == first["kpi_snapshots"]["forecast"]
    assert len(client.tickets.list()) == len(first["emitted_tickets"])
    assert "Executive overview" in second["report_markdown"]
