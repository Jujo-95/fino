import json
from unittest.mock import patch
import pytest
from finops_agent.agents.nvidia import NvidiaProvider
from finops_agent.agents.orchestrator import profile_node, build_graph
from finops_agent.agents.query_tools import AgentTools
from finops_agent.agents.agent_output import validate_output
from finops_agent.agents.specs import SPECIALIST_SPECS
from finops_agent.engine.script_store import ScriptStore
from test_run_audit import BODY, execute


def tool_call(name, args, call_id):
    return dict(id=call_id, type='function', function=dict(name=name, arguments=json.dumps(args)))


class FixtureProvider(NvidiaProvider):
    """Explicit test double. Never used by the application or live acceptance."""
    async def complete_for_report(self, messages, tools, max_tokens=None):
        return await self.complete(messages,tools)

    async def complete(self, messages, tools):
        prior = [json.loads(m['content']) for m in messages if m['role'] == 'tool']
        if not prior:
            calls = [tool_call('query_focus', {'query_id': 'services'}, 'q'),
                     tool_call('read_scripts', {}, 's'), tool_call('read_context', {}, 'c')]
        elif 'orchestrator' in messages[0]['content'] and not any('specialist' in p for p in prior):
            calls = [tool_call('request_refinement', {'specialist': 'anomaly',
                         'question': 'Recheck service evidence against client context.'}, 'r')]
        else:
            refs = [p['evidence_id'] for p in prior if 'evidence_id' in p]
            proposals = []
            if 'Check missing ownership tags' in messages[0]['content']:
                proposals = [dict(metric_key='unallocated_cost_pct', severity='MEDIUM', title='Revisar etiquetas',
                    justification='Evidencia de prueba', recommended_action='Revisar propiedad', evidence_ids=refs[:3])]
            calls = [tool_call('submit_analysis', dict(summary='Conclusión de prueba identificada.',
                                                       proposals=proposals, evidence_ids=refs[:3]), 'submit')]
        return dict(message=dict(role='assistant', content=None, tool_calls=calls), usage={'total_tokens': 10})


def test_scope_and_script_provenance(container, csv_path):
    container.client('acme').engine.ingest_focus_csv('acme', csv_path)
    state = {**BODY, **profile_node(container, BODY)}
    tools = AgentTools(container, state, 'allocation')
    result = tools.execute('query_focus', {'query_id': 'totals'}, 'one')
    assert result['rows'][0]['actual'] == 49110
    assert result['parameters']['client_id'] == 'acme'
    assert tools.queries[0]['executed_by'] == 'allocation'
    with pytest.raises(ValueError):
        tools.execute('query_focus', {'query_id': 'totals', 'client_id': 'other'}, 'bad')
    with pytest.raises(ValueError):
        tools.execute('query_focus', {'query_id': "read_csv('/etc/passwd')"}, 'bad')
    snapshot = tools.execute('read_scripts', {}, 'two')
    assert snapshot['data']['script_version'] == 'focus-baseline-v2'
    assert len(snapshot['data']['source_hash']) == 64
    store = ScriptStore(container.client('acme').engine)
    assert store.list()[0]['snapshot_id'] == state['kpi_snapshots']['snapshot_id']


def test_rejects_unsupported_findings(container, csv_path):
    container.client('acme').engine.ingest_focus_csv('acme', csv_path)
    tools = AgentTools(container, {**BODY, **profile_node(container, BODY)}, 'allocation')
    args = dict(summary='Test', proposals=[], evidence_ids=['invented', 'fake', 'unknown'])
    with pytest.raises(ValueError, match='Must call'):
        validate_output(args, tools, SPECIALIST_SPECS['allocation'])
    refs = [tools.execute(name, params, name)['evidence_id'] for name, params in
            [('query_focus', {'query_id': 'totals'}), ('read_scripts', {}), ('read_context', {})]]
    with pytest.raises(ValueError, match='Unknown evidence'):
        validate_output(args, tools, SPECIALIST_SPECS['allocation'])
    args['evidence_ids'] = refs
    args['proposals'] = [dict(metric_key='forecast_drift_rate', severity='HIGH', title='unsupported',
        justification='Test', recommended_action='Review', evidence_ids=refs)]
    with pytest.raises(ValueError, match='available metric'):
        validate_output(args, tools, SPECIALIST_SPECS['allocation'])


def test_native_loop_and_refinement_are_audited(container, csv_path):
    container.llm = FixtureProvider()
    frames, _, record = execute(container, csv_path)
    assert frames[-1]['node'] == '__done__'
    assert record['status'] == 'completed'
    assert len(record['events'][0]['payload']['trace']['queries']) == 3
    assert len(record['queries']) == 10  # 3 script + 5 specialist + orchestrator + revision
    traces = [event['payload']['trace'] for event in record['events']]
    assert all(t['engine'] == 'llm_agent' for t in traces[1:])
    assert len(traces[-1]['refinements']) == 1
    assert traces[-1]['refinements'][0]['trace']['node'] == 'anomaly'
    assert all(t['queries'] for t in traces[1:])
    assert 'Conclusión de prueba identificada.' in record['report_markdown']
    assert 'script_snapshots' in traces[0]['output']['storage']
    ticket = container.client('acme').tickets.list()[0]
    metric = next(m for m in traces[1]['metrics'] if m['key']=='unallocated_cost_pct')
    assert ticket.kpi_value == metric['value']
    assert ticket.estimated_monthly_impact_usd is None


def test_missing_key_never_falls_back(container, csv_path):
    container.llm = NvidiaProvider()
    with patch('finops_agent.agents.nvidia.settings', return_value={}):
        frames, _, record = execute(container, csv_path)
    assert frames[-1]['node'] == '__error__'
    assert 'NVIDIA_API_KEY' in record['error']
    assert record['report_markdown'] == ''
    assert record['partial_failure']['node'] == 'allocation'
    assert not container.client('acme').tickets.list()


@pytest.mark.asyncio
async def test_repeated_native_runs_keep_distinct_snapshots(container, csv_path):
    container.llm = FixtureProvider()
    container.client('acme').engine.ingest_focus_csv('acme', csv_path)
    graph = build_graph(container)
    first, second = await graph.ainvoke(BODY), await graph.ainvoke(BODY)
    assert first['kpi_snapshots']['snapshot_id'] != second['kpi_snapshots']['snapshot_id']
    store = ScriptStore(container.client('acme').engine)
    assert len(store.list()) == 2
    assert store.list()[0]['source_hash'] == store.list()[1]['source_hash']


@pytest.mark.parametrize('name', ['totals','daily','services','accounts','resources','tag_gaps','commitments'])
def test_all_query_templates_execute_with_scope(container, csv_path, name):
    container.client('acme').engine.ingest_focus_csv('acme', csv_path)
    tools = AgentTools(container, BODY, 'allocation')
    result = tools.execute('query_focus', {'query_id': name}, 'call')
    assert result['rows']
    assert result['parameters']['client_id'] == 'acme'
    assert len(result['rows']) <= 100
    filtered = tools.execute('query_focus', {'query_id': name, 'account': "x' OR 1=1 --"}, 'filtered')
    assert "x' OR 1=1 --" not in filtered['sql']
    if name != 'totals':
        assert filtered['rows'] == []
