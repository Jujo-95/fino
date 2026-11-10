import pytest
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.agents_v2.tools import finance_tools
from finops_agent.chat.tools import ToolContext
from finops_agent.chat.store import ChatStore
from finops_agent.consulting.diagnosis import diagnosis
from finops_agent.consulting.review import record_review
from test_consulting import confirm


def context(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    confirm(client, dict(source_cadence_days=1,data_latency_days=30))
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    thread.update(turn_id='review',ticket_refs=[])
    store.save(thread)
    return ToolContext(container,'acme',thread['thread_id'],'review')


def test_review_requires_query_and_expires_when_context_changes(container,csv_path):
    ctx = context(container,csv_path)
    with pytest.raises(ValueError,match='consulta real'):
        record_review(ctx,'anomaly','NO_ISSUES_DETECTED','Sin problemas en esta ventana',['invented'])
    tool = next(t for t in finance_tools(ctx) if t.name=='query_finance')
    query = tool.invoke(dict(sql='SELECT count(*) AS rows FROM focus_data_table'))
    record_review(ctx,'anomaly','NO_ISSUES_DETECTED','Conclusión de prueba acotada al periodo consultado',[query['evidence_id']])
    current = next(c for c in diagnosis(ctx.client)['capabilities'] if c['key']=='anomaly')
    assert current['state']=='NO_ISSUES_DETECTED' and current['evaluated_period']['start']=='2026-10-01'
    confirm(ctx.client,dict(objective='Control'))
    changed = next(c for c in diagnosis(ctx.client)['capabilities'] if c['key']=='anomaly')
    assert changed['last_review']['stale'] and changed['state']!='NO_ISSUES_DETECTED'


def test_review_cannot_clear_missing_inputs_with_a_successful_query(container,csv_path):
    ctx = context(container,csv_path)
    query = next(t for t in finance_tools(ctx) if t.name=='query_finance').invoke(dict(sql='SELECT sum(EffectiveCost) AS cost FROM focus_data_table'))
    with pytest.raises(ValueError,match='requisitos'):
        record_review(ctx,'budget','NO_ISSUES_DETECTED','Dentro de presupuesto',[query['evidence_id']])
