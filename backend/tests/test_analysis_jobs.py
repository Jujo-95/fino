"""Deterministic queue/clock/triage tests; no cloud or model invocation."""
import asyncio
from datetime import datetime,timezone
from finops_agent.config import atomic_write_text
from finops_agent.engine.analysis_queue import AnalysisQueue
from finops_agent.engine.run_audit import RunAuditStore
from finops_agent.models import RunRequest
from finops_agent.sources.remote_config import AnalysisSchedule
from finops_agent.engine.ticket_triage import review
from finops_agent.chat.operations import revision


def body():
    return RunRequest(client_id='acme',analysis_only=True,period_start_utc='2026-10-01',period_end_utc='2026-10-21')


def test_queue_claim_recovery_and_cancel_are_durable(tmp_path):
    queue = AnalysisQueue(tmp_path)
    first,created = queue.enqueue(body().model_dump(),'today')
    same,repeated = queue.enqueue(body().model_dump(),'manual')
    assert created and not repeated and same==first
    assert queue.claim()['id']==first and queue.claim() is None
    queue.close()
    restarted = AnalysisQueue(tmp_path)
    assert restarted.claim()['id']==first
    restarted.update(first,'cancelled')
    restarted.close()
    final = AnalysisQueue(tmp_path)
    assert final.claim() is None and final.get(first)['state']=='cancelled'
    final.close()


async def test_manual_analysis_deduplicates_and_persists_without_subscriber(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    first = container.jobs.start(body())
    assert container.jobs.start(body())['run_id']==first['run_id']
    store = RunAuditStore(client.workspace)
    for _ in range(100):
        record = store.read(first['run_id'])
        if record['status'] not in ('running','queued'):
            break
        await asyncio.sleep(.01)
    assert record['status'] in ('completed','partial')
    assert record['analysis']['analysis_id']==first['run_id'] and not record['report_markdown']
    ticket = next(t for t in client.tickets.list() if t.is_new)
    before = revision(ticket)
    reviewed = review(client,ticket.ticket_id)
    after = next(t for t in client.tickets.list() if t.ticket_id==ticket.ticket_id)
    assert not reviewed['is_new'] and reviewed['needs_attention'] and revision(after)==before
    await container.jobs.shutdown()


async def test_clock_timezone_catchup_and_no_enable_by_default(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    jobs = container.jobs.analysis
    now = datetime(2026,10,26,10,59,tzinfo=timezone.utc)
    jobs.tick(now)
    assert not RunAuditStore(client.workspace).list()
    atomic_write_text(client.workspace/'analysis-schedule.json',AnalysisSchedule(enabled=True).model_dump_json())
    jobs.tick(now)
    assert not RunAuditStore(client.workspace).list()
    jobs.tick(datetime(2026,10,26,11,0,tzinfo=timezone.utc))
    jobs.tick(datetime(2026,10,26,11,1,tzinfo=timezone.utc))
    assert len(RunAuditStore(client.workspace).list())==1
    record = RunAuditStore(client.workspace).list()[0]
    assert jobs.stop('another',record['run_id']) is False
    assert jobs.stop('acme',record['run_id'])
    await container.jobs.shutdown()
    assert jobs.queue is not None
