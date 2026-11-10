from datetime import date
from types import SimpleNamespace
import csv
import pytest
from finops_agent.lab.generator import generate
from finops_agent.lab.scenarios import SCENARIOS
from finops_agent.engine.duckdb_engine import DuckDBFocusEngine
from finops_agent.agents_v2.snapshots import read_snapshots, execute_case


@pytest.mark.parametrize('client_id',list(SCENARIOS))
def test_generated_focus_executes_community_cases_without_schema_hunting(tmp_path,client_id):
    scenario = SCENARIOS[client_id]
    manifest = generate(scenario,tmp_path,date(2026,10,1),7)
    engine = DuckDBFocusEngine(':memory:')
    try:
        for part in manifest['partitions']:
            path = tmp_path/client_id/part['key']
            with path.open() as stream:
                row = next(csv.DictReader(stream))
            assert row['BillingPeriodEnd']=='2026-11-01'
            assert row['ServiceProviderName'] and row['PricingQuantity']
            engine.ingest_focus_csv(client_id,path)
            assert engine.ingest_focus_csv(client_id,path)==0
        client = SimpleNamespace(engine=engine,workspace=tmp_path,profile=scenario.profile())
        result = read_snapshots(client,'2026-10-01','2026-10-08')
        assert result==read_snapshots(client,'2026-10-01','2026-10-08')
        assert result['coverage']['ok']+result['coverage']['empty']>=55
        assert result['coverage']['error']==0
        assert all('not found' not in row.get('reason','') for row in result['results'])
        assert execute_case(client,1,'2026-10-01','2026-11-01')['status'] in ('ok','empty')
    finally:
        engine.close()
