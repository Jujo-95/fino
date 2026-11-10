from concurrent.futures import ThreadPoolExecutor
import pytest
from finops_agent.consulting.workflow import sync_tasks, task
from finops_agent.models import TicketUpdate
from finops_agent.engine.ticket_manager import ticket_markdown
from test_consulting import confirm


def test_native_onboarding_is_idempotent_and_has_no_fake_kpis(container):
    client = container.client('acme')
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: sync_tasks(client), range(3)))
    tickets = client.tickets.list()
    assert len(tickets)==len({t.workflow_key for t in tickets})
    assert all(t.ticket_kind=='onboarding' and t.kpi_value is None
               and t.estimated_monthly_impact_usd is None for t in tickets)
    assert all('Tarea sin indicador medido' in ticket_markdown(t) for t in tickets)


def test_confirmation_completes_native_task_without_reopening_user_decisions(container):
    client = container.client('acme')
    sync_tasks(client)
    before = {t.workflow_key:t for t in client.tickets.list()}
    client.tickets.update(before['requirement:objective'].ticket_id,
                         TicketUpdate(status='SNOOZED', resolution_note='Revisar el próximo mes'))
    confirm(client, dict(monthly_budget=42000, objective='Controlar el gasto'))
    sync_tasks(client)
    after = {t.workflow_key:t for t in client.tickets.list()}
    assert after['requirement:monthly_budget'].status=='IMPLEMENTED'
    assert after['requirement:objective'].status=='SNOOZED'
    sync_tasks(client)
    assert len(client.tickets.list())==len(before)


def test_review_tasks_share_indicators_and_scope_without_asserting_findings(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    sync_tasks(client)
    tickets = client.tickets.list()
    reviews = [t for t in tickets if t.ticket_kind=='analysis']
    assert {'allocation','anomaly-management','budgeting','forecasting'} <= {t.capability for t in reviews}
    assert all(t.kpi_value is None and t.estimated_monthly_impact_usd is None for t in reviews)
    budget = next(t for t in reviews if t.capability=='budgeting')
    dependency = next(t for t in tickets if t.workflow_key=='requirement:monthly_budget')
    assert dependency.ticket_id in budget.action_details.dependencies


def test_administrative_tasks_cannot_claim_savings_or_become_unmeasured_findings():
    values = task('test','Confirmar presupuesto','budgeting','Confirmar importe','onboarding').model_dump()
    with pytest.raises(ValueError):
        task_model = {**values,'estimated_monthly_impact_usd':100}
        type(task('test','Confirmar','budgeting','Confirmar','onboarding')).model_validate(task_model)
    with pytest.raises(ValueError):
        from finops_agent.models import Finding
        Finding.model_validate({**values,'ticket_kind':'finding'})
