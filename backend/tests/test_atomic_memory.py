import json
from finops_agent.engine.ticket_provenance import contributors_for, historical_contributors
from unittest.mock import patch
import pytest
from finops_agent.models import Finding, TicketUpdate, TicketContributor


@pytest.fixture
def finding():
    return Finding(capability="anomaly-management", maturity_tier="Walk", allocation_mode="N/A",
        severity="HIGH", sub_account_id="ml-platform", service_name="Vertex AI", period_bucket="2026-10",
        kpi_name="anomaly_unpredicted_variance", kpi_value=1200, estimated_monthly_impact_usd=36000,
        title="GPU training spike", evidence_summary="Anomaly cost - baseline = 1200 USD/day", recommended_action="Review GPU training",
        capability_citation_url="https://www.finops.org/framework/capabilities/anomaly-management/")


def test_dedup_and_document_recall(container, finding):
    client = container.client("acme")
    first = client.tickets.create(finding)
    assert client.tickets.create(finding).ticket_id == first.ticket_id
    client.tickets.update(first.ticket_id, TicketUpdate(status="FALSE_POSITIVE", resolution_note="Approved GPU training until October 30"))
    results = container.memory.retrieve("ml-platform GPU approved training", "acme")
    assert any("FALSE_POSITIVE" in row["text"] and "October 30" in row["text"] for row in results)
    assert len(list((client.workspace / "tickets").glob("*.md"))) == 1
    client.tickets.recover()
    assert "FALSE_POSITIVE" in (client.workspace / "tickets/FIN-001.md").read_text()


def test_rollback_on_file_failure(container, finding):
    client = container.client("acme")
    with patch("finops_agent.engine.ticket_manager.atomic_write_text", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            client.tickets.create(finding)
    assert client.tickets.list() == []
    assert client.engine.conn.execute("SELECT count(*) FROM context_documents WHERE doc_id != 'profile'").fetchone()[0] == 0


def test_planned_context_and_expiry(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    assert len(container.overview('acme')['spikes']) == 1
    note = '''---
planned_events:
  - sub_account_id: ml-platform
    service_name: Vertex AI
    start_utc: '2026-10-19'
    end_utc: '2026-10-22'
    approved: true
---
GPU training approved for the product launch.
'''
    client.tickets.index_context('note:planned-training', note)
    result = container.overview('acme')
    assert result['spikes'] == []
    assert result['excluded_baseload'] == ['ml-platform:Vertex AI']
    client.tickets.index_context('note:planned-training',note.replace('2026-10-22','2026-10-20'))
    assert len(container.overview('acme')['spikes']) == 1


def test_distinct_metrics_and_revised_proposals(container, finding):
    tickets = container.client('acme').tickets
    first = tickets.create(finding)
    revised = tickets.create(finding.model_copy(update={'recommended_action': 'Revised action'}))
    assert revised.ticket_id == first.ticket_id
    assert revised.recommended_action == 'Revised action'
    second = tickets.create(finding.model_copy(update={'kpi_name': 'genai_anomaly_detection_rate'}))
    assert second.ticket_id != first.ticket_id
    tickets.update(first.ticket_id, TicketUpdate(status='FALSE_POSITIVE', resolution_note='Approved workload'))
    preserved = tickets.create(finding)
    assert preserved.status == 'FALSE_POSITIVE'
    assert preserved.resolution_note == 'Approved workload'


def test_existing_documents_migrate_without_graph_dependency(tmp_path):
    import duckdb
    from finops_agent.engine.duckdb_engine import DuckDBFocusEngine
    path = tmp_path / 'legacy.duckdb'
    connection = duckdb.connect(str(path))
    connection.execute('CREATE TABLE graph_documents(doc_id VARCHAR PRIMARY KEY, content VARCHAR)')
    connection.execute("INSERT INTO graph_documents VALUES ('note:prior','Approved plan')")
    connection.close()
    engine = DuckDBFocusEngine(path)
    try:
        assert engine.conn.execute('SELECT content FROM context_documents').fetchone()[0] == 'Approved plan'
    finally:
        engine.close()




def test_attribution_matches_scope_and_multiple_actual_nodes(finding):
    document = finding.model_dump()
    traces = [dict(node=node, findings=[document]) for node in ('anomaly', 'budgeting')]
    traces.append(dict(node='allocation', findings=[{**document, 'service_name': 'Other'}]))
    result = contributors_for(document, traces, 'run-1')
    assert [(item.agent_id, item.role) for item in result] == [
        ('anomaly', 'detected'), ('budgeting', 'detected'), ('orchestrator', 'consolidated')]


def test_contributors_survive_dedup_resolution_and_recovery(container, finding):
    client = container.client('acme')
    contributor = TicketContributor(agent_id='anomaly', role='detected', run_id='run-1')
    first = client.tickets.create(finding, [contributor])
    client.tickets.create(finding, [contributor])
    client.tickets.update(first.ticket_id, TicketUpdate(status='FALSE_POSITIVE', resolution_note='Approved'))
    other = TicketContributor(agent_id='orchestrator', role='consolidated', run_id='run-2')
    revised = client.tickets.create(finding, [other])
    assert revised.contributors == [contributor, other]
    assert revised.status == 'FALSE_POSITIVE' and revised.resolution_note == 'Approved'
    client.tickets.recover()
    assert client.tickets.list()[0].contributors == revised.contributors
    assert 'run-1' in (client.workspace / 'tickets/FIN-001.md').read_text()


def test_legacy_attribution_requires_recorded_ticket_link(container, finding):
    client = container.client('acme')
    ticket = client.tickets.create(finding)
    assert historical_contributors([ticket], client.workspace)[0]['contributors'] == []
    directory = client.workspace / 'audit_runs'
    directory.mkdir(exist_ok=True)
    traces = [dict(node='anomaly', findings=[finding.model_dump()]),
              dict(node='synthesize', output=dict(ticket_links=[dict(fingerprint=ticket.fingerprint)]))]
    record = dict(run_id='recorded-run', events=[dict(payload=dict(trace=t)) for t in traces])
    (directory / 'record.json').write_text(json.dumps(record))
    result = historical_contributors([ticket], client.workspace)[0]['contributors']
    assert [item['agent_id'] for item in result] == ['anomaly', 'orchestrator']
    assert result[0]['run_id'] == 'recorded-run'
