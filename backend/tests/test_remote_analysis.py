"""Offline cloud doubles: real Parquet/DuckDB, no production credentials or LLM."""
from datetime import date
import threading
import pytest
from finops_agent.sources.remote_config import RemoteSource,save_remote
from finops_agent.agents_v2.sql import query
from finops_agent.sources.bigquery_remote import translate
from finops_agent.engine.analysis_service import run_analysis
from finops_agent.models import RunRequest


@pytest.fixture
def remote(container,csv_path,tmp_path,monkeypatch):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    path = tmp_path/'billing.parquet'
    client.engine.conn.execute('COPY (SELECT * EXCLUDE(client_id,file_hash,row_key) FROM focus_usage) TO ? (FORMAT PARQUET)',[str(path)])
    client.engine.conn.execute('DELETE FROM focus_usage')
    source = RemoteSource(kind='s3',bucket='customer-focus',prefix='costs/',available_start=date(2026,10,1),available_end=date(2026,11,1))
    save_remote(client,source)
    from finops_agent.sources import parquet_remote
    monkeypatch.setattr(parquet_remote,'objects',lambda *args:[dict(name='costs/2026-10-01.parquet',size=path.stat().st_size,version='v1')])
    monkeypatch.setattr(parquet_remote,'authenticate',lambda *args:[str(path)])
    return client


def test_remote_query_cache_and_raw_rows_stay_in_customer_source(remote):
    sql = 'SELECT sum(EffectiveCost) AS cost FROM focus_data_table'
    first = query(remote,sql,'2026-10-01','2026-11-01')
    second = query(remote,sql,'2026-10-01','2026-11-01')
    assert float(first['rows'][0]['cost'])==49110
    assert not first['cache_hit'] and second['cache_hit']
    assert remote.engine.conn.execute('SELECT count(*) FROM focus_usage').fetchone()[0]==0
    assert query(remote,sql,'2026-09-01','2026-10-01')['rows'][0]['cost'] is None
    with pytest.raises(ValueError):
        query(remote,"SELECT * FROM read_parquet('s3://another-client/*')",'2026-10-01','2026-11-01')


def test_remote_measurements_create_native_tasks_without_narrative(container,remote):
    body = RunRequest(client_id='acme',period_start_utc='2026-10-01',period_end_utc='2026-10-21',analysis_only=True)
    first = run_analysis(container,body,'a'*32,threading.Event())
    second = run_analysis(container,body,'b'*32,threading.Event())
    assert first['overview']['actual']==49110
    assert first['findings'] and first['actions']
    assert second['status']=='skipped' and not second['actions']
    assert {a['ticket_id'] for a in first['actions']}=={t.ticket_id for t in remote.tickets.list()}
    assert all(row['model_calls']==0 for row in first['coverage'])
    assert 'report_markdown' not in first
    assert container.overview('acme')['actual']==49110
    assert remote.engine.conn.execute('SELECT count(*) FROM focus_usage').fetchone()[0]==0


def test_bigquery_translation_preserves_utc_json_and_parameters():
    sql = 'SELECT CAST(Tags AS JSON),CAST(ChargePeriodStart AS TIMESTAMP),json_extract_string(Tags,\'/owner\') FROM "project.dataset.table" WHERE ChargePeriodStart>=$start_utc'
    result = translate(sql,{'tags':'STRING'})
    assert 'PARSE_JSON' in result and '$."owner"' in result
    assert 'AS TIMESTAMP' in result and 'AS DATETIME' not in result
    assert '@start_utc' in result and '`project.dataset.table`' in result


def test_retained_measurements_survive_cache_expiry_and_context_change(container,remote,monkeypatch):
    body = RunRequest(client_id='acme',period_start_utc='2026-10-01',period_end_utc='2026-10-21',analysis_only=True)
    run_analysis(container,body,'c'*32,threading.Event())
    for file in (remote.workspace/'query_cache').glob('*'):
        file.unlink()
    from finops_agent.sources import remote_analytics
    def unexpected_scan(*args,**kwargs):
        raise AssertionError('Unchanged source must use retained aggregates')
    monkeypatch.setattr(remote_analytics,'remote_result',unexpected_scan)
    remote.profile = remote.profile.model_copy(update={'previous_forecast_spend':50000})
    result = run_analysis(container,body,'d'*32,threading.Event())
    assert result['overview']['actual']==49110
    assert all(q['reused_retained_measurement'] for q in result['evidence'])
    assert next(m for m in result['measurements'] if m['key']=='forecast_drift_rate')['value'] is not None
