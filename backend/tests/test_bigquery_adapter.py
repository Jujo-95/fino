"""Official SDK-shaped doubles verify billing guards and cancellation offline."""
from datetime import date
from types import SimpleNamespace
import pytest
from finops_agent.sources.bigquery_remote import BigQueryRemote
from finops_agent.sources.remote_config import RemoteSource


class Job:
    job_id='fixture-job'
    total_bytes_processed=100
    cache_hit=False
    cancelled=False
    fails=False
    def result(self,**kwargs):
        if self.fails:
            raise TimeoutError('offline fixture')
        return [{'cost':12.5}]
    def cancel(self):
        self.cancelled=True


class SDK:
    def __init__(self):
        self.job=Job()
        self.calls=[]
        self.bytes=100
    def get_table(self,*args,**kwargs):
        return SimpleNamespace(schema=[SimpleNamespace(name='Tags',field_type='STRING')],modified='v1',etag='fixture')
    def query(self,sql,job_config,**kwargs):
        self.calls.append((sql,job_config))
        return SimpleNamespace(total_bytes_processed=self.bytes) if job_config.dry_run else self.job
    def close(self):
        pass


def remote(client,monkeypatch):
    from google.cloud import bigquery
    from finops_agent.sources import bigquery_remote
    sdk=SDK()
    monkeypatch.setattr(bigquery,'Client',lambda **kwargs:sdk)
    monkeypatch.setattr(bigquery_remote,'google_credentials',lambda *args:None)
    source=RemoteSource(kind='bigquery',project='billing-project',table='customer.focus.billing',
        available_start=date(2026,10,1),available_end=date(2026,11,1),max_source_bytes=1048576)
    return BigQueryRemote(client,source,'2026-10-01','2026-11-01'),sdk


def test_dry_run_blocks_expensive_scan_before_execution(container,monkeypatch):
    reader,sdk=remote(container.client('acme'),monkeypatch)
    sdk.bytes=1048577
    with pytest.raises(ValueError,match='bytes'):
        reader.execute('SELECT sum(EffectiveCost) AS cost FROM "customer.focus.billing"',{})
    assert len(sdk.calls)==1


def test_sdk_uses_parameterized_query_and_cancels_timeout(container,monkeypatch):
    reader,sdk=remote(container.client('acme'),monkeypatch)
    result=reader.execute('SELECT sum(EffectiveCost) AS cost FROM "customer.focus.billing" WHERE ChargePeriodStart>=$start_utc',{'start_utc':'2026-10-01'})
    assert result==[{'cost':12.5}]
    sql,config=sdk.calls[-1]
    assert '@start_utc' in sql and config.maximum_bytes_billed==1048576
    assert config.query_parameters[0].type_=='TIMESTAMP' and reader.stats['job_id']=='fixture-job'
    sdk.job.fails=True
    with pytest.raises(TimeoutError):
        reader.execute('SELECT EffectiveCost FROM "customer.focus.billing"',{})
    assert sdk.job.cancelled
