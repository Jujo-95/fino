import hashlib
import json
from datetime import date
from pathlib import Path
import pytest
from finops_agent.lab.generator import generate, daily_rows
from finops_agent.lab.scenarios import SCENARIOS


@pytest.mark.parametrize('client_id',list(SCENARIOS))
def test_reproducible_partitions_and_scenario_logic(tmp_path: Path, client_id: str) -> None:
    scenario = SCENARIOS[client_id]
    first = generate(scenario,tmp_path,date(2026,7,23))
    path = tmp_path/client_id/first['partitions'][0]['key']
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert generate(scenario,tmp_path,date(2026,7,23))==first
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    normal,spike,fixed = [daily_rows(scenario,date(2026,7,23),i,42) for i in [74,75,85]]
    assert float(spike[3]['EffectiveCost'])>float(normal[3]['EffectiveCost'])*3
    assert 'owner' not in json.loads(normal[4]['Tags'])
    assert 'owner' in json.loads(fixed[4]['Tags'])
    assert float(fixed[1]['EffectiveCost'])<float(normal[1]['EffectiveCost'])/3
    assert sum(float(r['EffectiveCost']) for r in normal[:2])==pytest.approx(
        sum(float(r['EffectiveCost']) for r in fixed[:2]),abs=.00001)
    assert all(str(r['ResourceId']).startswith(client_id+'/') for r in fixed)
    assert len(first['partitions'])==90
    for part in first['partitions']:
        assert (tmp_path/client_id/part['key']).exists()


@pytest.mark.parametrize('days',[0,-1,367])
def test_generator_rejects_invalid_horizon(tmp_path: Path, days: int) -> None:
    with pytest.raises(ValueError):
        generate(SCENARIOS['lab-fintech'],tmp_path,date(2026,7,23),days)
