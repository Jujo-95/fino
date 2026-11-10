import hashlib
import pytest
from finops_agent.agents_v2.registry import definitions, use_cases, ORCHESTRATOR
from finops_agent.agents_v2.sql import query
from finops_agent.agents_v2.snapshots import read_snapshots
from finops_agent.chat.agent_context import instructions
from finops_agent.chat.models import ThreadRequest
from finops_agent.chat.store import ChatStore
from finops_agent.chat.tools import chat_tools


@pytest.mark.parametrize('agent_id',list(definitions()))
def test_imported_roles_and_contracts_preserved(agent_id):
    row = definitions()[agent_id]
    assert ThreadRequest(agent_id=agent_id).agent_id==agent_id
    assert hashlib.sha256(row['source'].encode()).hexdigest()==row['source_sha256']
    prompt = instructions(agent_id)
    assert 'App runtime contract' in prompt
    if agent_id==ORCHESTRATOR:
        assert 'verified_state' in prompt and '.coda/memory/' not in prompt
    else:
        assert row['prompt'] in prompt
    assert 'Never access' in prompt and 'read_use_case_snapshots' in prompt
    assert len(use_cases())==60 and all(item['sql'] for item in use_cases().values())


@pytest.mark.parametrize('statement',[
    'SELECT sum(EffectiveCost) AS cost FROM focus_data_table',
    'WITH a AS (SELECT EffectiveCost FROM focus_data_table) SELECT sum(EffectiveCost) AS cost FROM a',
    'SELECT sum(EffectiveCost) AS cost FROM focus_data_table WHERE 1=1 OR 1=1',
    'SELECT sum(a.EffectiveCost) AS cost FROM focus_data_table a WHERE a.ServiceName IS NOT NULL',
])
def test_sql_scope_is_injected_not_chosen_by_model(container,csv_path,statement):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    client.engine.ingest_focus_csv('another',csv_path)
    result = query(client,statement,'2026-10-01','2026-11-01')
    assert result['rows'][0]['cost']==49110 and result['client_id']=='acme'
    empty = query(client,statement,'2026-09-01','2026-10-01')
    assert empty['rows'][0]['cost'] is None


@pytest.mark.parametrize('statement',[
    "SELECT * FROM read_csv_auto('/etc/passwd')",
    'SELECT * FROM tickets_ledger',
    'SELECT * FROM other.focus_usage',
    'SELECT * FROM focus_data_table; DROP TABLE focus_usage',
    "SELECT getenv('NVIDIA_API_KEY') FROM focus_data_table",
    'SELECT * INTO stolen FROM focus_data_table',
    'WITH focus_data_table AS (SELECT 1) SELECT * FROM focus_data_table',
    "SELECT * FROM query('SELECT * FROM tickets_ledger')",
])
def test_unsafe_sql_is_rejected(container,statement):
    with pytest.raises(ValueError):
        query(container.client('acme'),statement,'2026-10-01','2026-11-01')


def test_reference_snapshots_reused_and_unavailable_is_not_zero(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    first = read_snapshots(client,'2026-10-01','2026-11-01')
    second = read_snapshots(client,'2026-10-01','2026-11-01')
    assert first==second and sum(first['coverage'].values())==60
    assert first['coverage']['unavailable']>0
    assert first['coverage']['ok']+first['coverage']['empty']>0
    assert len(list((client.workspace/'use_case_snapshots').glob('*.json')))==1
    assert read_snapshots(client,'2026-09-01','2026-10-01')['evidence_id']!=first['evidence_id']


@pytest.mark.asyncio
async def test_v2_tools_keep_originals_and_add_scoped_queries(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    for agent in [ORCHESTRATOR,'v2-budget-anomaly-operator','anomaly']:
        thread = ChatStore(client).create(agent)
        thread.update(turn_id='test',ticket_refs=[])
        ChatStore(client).save(thread)
        tools = {t.name:t for t in chat_tools(container,'acme',thread['thread_id'],'test')}
        if agent=='anomaly':
            assert 'query_focus' in tools and 'query_finance' not in tools
            continue
        assert {'query_finance','get_schema','read_report_changes','read_use_case_snapshots'}<=tools.keys()
        assert ('consult_specialist' in tools)==(agent==ORCHESTRATOR)
        result = await tools['query_finance'].ainvoke(dict(sql='SELECT sum(EffectiveCost) AS cost FROM focus_data_table'))
        assert result['rows'][0]['cost']==49110
