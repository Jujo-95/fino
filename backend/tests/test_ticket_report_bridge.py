from uuid import uuid4
import pytest
from finops_agent.chat.models import PlanRequest, ChatMessage, ResumeRequest
from finops_agent.chat.store import ChatStore
from finops_agent.engine.run_audit import RunAuditStore
from finops_agent.engine.report_guard import repeat_prompt, require_confirmation, ReportConfirmationRequired
from finops_agent.models import RunRequest
from finops_agent.agents_v2.registry import ORCHESTRATOR
from test_chat_operations import ops as operations_fixture
from test_chat_graph import wait_job
from test_agents_v2_flow import call

BODY = dict(client_id='acme',run_mode='daily',period_start_utc='2026-10-01',period_end_utc='2026-10-21',billing_currency='USD')


def completed(client, body=None):
    store = RunAuditStore(client.workspace)
    record = store.create(body or BODY,'explicit-test-double')
    store.finish(record,'completed')
    return record


def new_finding(ops):
    finding = ops.client.tickets.list()[0].model_dump(include=set(ops.client.tickets.list()[0].__class__.__bases__[0].model_fields))
    finding.update(kpi_name='new_metric',title='New measured finding')
    finding['action_details'] = dict(steps=['Revisar el alcance con el responsable','Aplicar las etiquetas acordadas'],
        completion_criterion='Comprobar las etiquetas en la siguiente exportación.')
    return finding


def test_mixed_batch_creates_real_ids_only_after_approval(container):
    ops = operations_fixture.__wrapped__(container)
    ticket = ops.tickets(['FIN-001'])[0]
    request = PlanRequest(changes=[dict(action='create',finding=new_finding(ops),reason='Measured evidence'),
        dict(ticket_id='FIN-001',expected_revision=ticket['revision'],fields=dict(title='Updated finding'),reason='New evidence')])
    plan = ops.plan(request,'thread','turn',report_run_id='a'*32)
    assert len(ops.client.tickets.list())==2
    result = ops.apply(plan['plan_id'],'thread','command',dict(actor='local-user',message_id='approved'))
    assert result['report_run_id']=='a'*32
    assert [t['ticket_id'] for t in result['tickets']]==['FIN-003','FIN-001']
    assert ops.tickets(['FIN-001'])[0]['title']=='Updated finding'
    assert ops.apply(plan['plan_id'],'thread','command',dict(actor='local-user',message_id='approved'))==result
    with pytest.raises(ValueError,match='existe'):
        ops.plan(PlanRequest(changes=[request.changes[0]]),'thread','turn-2')


def test_concurrent_duplicate_aborts_whole_batch(container):
    ops = operations_fixture.__wrapped__(container)
    finding = new_finding(ops)
    ticket = ops.tickets(['FIN-001'])[0]
    plan = ops.plan(PlanRequest(changes=[dict(action='create',finding=finding,reason='Evidence'),
        dict(ticket_id='FIN-001',expected_revision=ticket['revision'],target_status='APPROVED',reason='Decision')]),'thread','turn')
    from finops_agent.models import Finding
    ops.client.tickets.create(Finding(**finding))
    with pytest.raises(ValueError,match='duplicado'):
        ops.apply(plan['plan_id'],'thread','command',dict(actor='local-user',message_id='approved'))
    assert ops.tickets(['FIN-001'])[0]['status']=='PROPOSED'


def test_repeat_guard_is_period_and_client_bound(container):
    client = container.client('acme')
    record = completed(client)
    prompt = repeat_prompt(client,BODY['period_start_utc'],BODY['period_end_utc'])
    assert prompt['existing_run_id']==record['run_id']
    with pytest.raises(ReportConfirmationRequired):
        require_confirmation(client,RunRequest(**BODY,force_reanalysis=True,force_reason='Not user approval'))
    require_confirmation(client,RunRequest(**BODY,repeat_confirmation=prompt['confirmation_id']))
    assert repeat_prompt(client,'2026-09-01','2026-09-30') is None
    record['finished_at_utc']='2020-01-01T00:00:00Z'
    RunAuditStore(client.workspace).save(record)
    assert repeat_prompt(client,BODY['period_start_utc'],BODY['period_end_utc']) is None


class RepeatDouble:
    calls=0
    async def complete(self,messages,tools):
        self.calls+=1
        if messages[-1]['role']=='user':
            return call('start_report_job',{})
        return dict(message=dict(role='assistant',content='Decisión recibida.'))


@pytest.mark.asyncio
@pytest.mark.parametrize('decision',['approve','reject'])
async def test_chat_repeat_pauses_before_job_creation(container,csv_path,decision):
    client=container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    container.llm=RepeatDouble()
    store=ChatStore(client)
    thread=store.create(ORCHESTRATOR)
    from finops_agent.chat.tools import ToolContext
    scope=ToolContext(container,'acme',thread['thread_id'],'test').evidence.current().state
    completed(client,{**BODY,'period_start_utc':scope['period_start_utc'],'period_end_utc':scope['period_end_utc']})
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Prepara el informe',message_id=uuid4().hex))
    waiting=await wait_job(container,thread)
    assert waiting['status']=='waiting',waiting.get('error')
    assert waiting['pending_report']['kind']=='repeat_report' and not container.jobs.tasks
    assert len(RunAuditStore(client.workspace).list())==1 and container.llm.calls==1
    container.chat.start('acme',thread['thread_id'],ResumeRequest(decision=decision,
        plan_ids=[waiting['pending_report']['confirmation_id']],message_id=uuid4().hex))
    result=await wait_job(container,thread)
    assert result['status']=='ready',result.get('error')
    assert len(RunAuditStore(client.workspace).list())==(2 if decision=='approve' else 1)


@pytest.mark.asyncio
async def test_saved_report_proposes_native_tickets_then_applies(container,csv_path):
    ops=operations_fixture.__wrapped__(container)
    ops.client.engine.ingest_focus_csv('acme',csv_path)
    finding=new_finding(ops)
    class ReportDouble:
        async def complete(self,messages,tools):
            if messages[-1]['role']=='user':
                return call('save_report',dict(markdown='# Informe\nHallazgo medido.',structured_report=dict(
                    report=dict(clientId='acme',period='2026-10',currency='USD'),summary={},findings=[],
                    tickets=dict(proposedActions=[dict(action='create',finding=finding,reason='Evidencia del informe')]))))
            return dict(message=dict(role='assistant',content='Propuesta preparada.'))
    container.llm=ReportDouble()
    store=ChatStore(ops.client)
    thread=store.create(ORCHESTRATOR)
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Prepara el informe',message_id=uuid4().hex))
    waiting=await wait_job(container,thread)
    assert waiting['status']=='waiting',waiting.get('error')
    assert len([t for t in ops.client.tickets.list() if t.ticket_kind=='finding'])==2
    report_id=RunAuditStore(ops.client.workspace).list()[0]['run_id']
    container.chat.start('acme',thread['thread_id'],ResumeRequest(decision='approve',
        plan_ids=[waiting['pending'][0]['plan_id']],message_id=uuid4().hex))
    result=await wait_job(container,thread)
    assert result['status']=='ready',result.get('error')
    assert len([t for t in ops.client.tickets.list() if t.ticket_kind=='finding'])==3
    from finops_agent.chat.report_ticket_links import report_ticket_links
    created = next(t for t in ops.client.tickets.list() if t.kpi_name==finding['kpi_name'])
    assert report_ticket_links(ops.client,report_id)==[created.ticket_id]


def test_http_repeat_returns_reviewable_conflict_without_job(container):
    from fastapi.testclient import TestClient
    from finops_agent.api.server import app
    from finops_agent.api.routes import get_container
    completed(container.client('acme'))
    app.dependency_overrides[get_container]=lambda:container
    try:
        with TestClient(app) as client:
            for endpoint in ('/api/v1/runs','/api/v1/runs/stream'):
                response=client.post(endpoint,json=BODY)
                assert response.status_code==409,response.text
                assert response.json()['detail']['code']=='report_exists'
            assert not container.jobs.tasks
    finally:
        app.dependency_overrides.clear()


def test_mixed_batch_disk_failure_rolls_back_new_file_and_edit(container):
    from unittest.mock import patch
    from finops_agent.engine.ticket_manager import atomic_write_text
    ops=operations_fixture.__wrapped__(container)
    ticket=ops.tickets(['FIN-001'])[0]
    plan=ops.plan(PlanRequest(changes=[dict(action='create',finding=new_finding(ops),reason='Evidence'),
        dict(ticket_id='FIN-001',expected_revision=ticket['revision'],fields=dict(title='Changed'),reason='Evidence')]),'thread','turn')
    count=0
    def fail(path,text):
        nonlocal count
        count+=1
        if count==2:
            raise OSError('Explicit disk failure')
        atomic_write_text(path,text)
    with patch('finops_agent.engine.ticket_manager.atomic_write_text',side_effect=fail):
        with pytest.raises(OSError):
            ops.apply(plan['plan_id'],'thread','cmd',dict(actor='local-user',message_id='approved'))
    assert len(ops.client.tickets.list())==2
    assert ops.tickets(['FIN-001'])[0]['title']==ticket['title']
    assert not (ops.client.workspace/'tickets/FIN-003.md').exists()
