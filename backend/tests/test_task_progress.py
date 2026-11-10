from unittest.mock import patch
import pytest
from finops_agent.models import Finding, TicketUpdate
from finops_agent.consulting.progress_objectives import objectives, exclude_step, next_cycle
from finops_agent.consulting.progress_history import history_summary, read_events
from finops_agent.consulting.progress import attention, progress
from finops_agent.consulting.actions import action_summary


def create(client, service='Storage'):
    return client.tickets.create(Finding(capability='allocation',maturity_tier='Walk',allocation_mode='Showback',
        severity='HIGH',sub_account_id='platform',service_name=service,period_bucket='2026-10',
        kpi_name='unallocated_cost_pct',kpi_value=10,estimated_monthly_impact_usd=None,
        title='Confirmar responsable '+service,evidence_summary='10% sin responsable',
        recommended_action='Confirmar el equipo responsable',capability_citation_url='https://www.finops.org/framework/capabilities/allocation/'))


def rows(client):
    return [t.model_dump(mode='json') for t in client.tickets.list()]


def test_frozen_scope_reopen_and_next_cycle(container):
    client=container.client('acme')
    first=create(client)
    goal=objectives(client,rows(client))[0]
    create(client,'Compute')
    assert objectives(client,rows(client))[0]['total']==1
    client.tickets.update(first.ticket_id,TicketUpdate(status='RESOLVED',resolution_note='Responsable confirmado'))
    assert objectives(client,rows(client))[0]['percent']==100
    next_cycle(client)
    assert len(objectives(client,rows(client)))==2
    client.tickets.update(first.ticket_id,TicketUpdate(status='PROPOSED',resolution_note='Confirmación revocada'))
    revised=next(g for g in objectives(client,rows(client)) if g['id']==goal['id'])
    assert revised['percent']==0
    assert history_summary(client,rows(client))['resolved_total']==0


def test_discard_does_not_count_and_scope_adjustment_is_explicit(container):
    client=container.client('acme')
    first=create(client)
    create(client,'Compute')
    goal=objectives(client,rows(client))[0]
    client.tickets.update(first.ticket_id,TicketUpdate(status='FALSE_POSITIVE',resolution_note='Error en asignación de origen'))
    assert objectives(client,rows(client))[0]['completed']==0
    with pytest.raises(ValueError):
        exclude_step(client,goal['id'],first.ticket_id,99)
    changed=exclude_step(client,goal['id'],first.ticket_id,1)
    assert changed['version']==2 and changed['history'][0]['reason']
    assert exclude_step(client,goal['id'],first.ticket_id,1)==changed
    assert objectives(client,rows(client))[0]['total']==1
    with pytest.raises(KeyError):
        exclude_step(client,'other-client-objective',first.ticket_id,1)


def test_committed_events_only_and_no_double_count_for_notes(container):
    client=container.client('acme')
    first=create(client)
    with patch('finops_agent.engine.ticket_manager.atomic_write_text',side_effect=OSError('disk full')):
        with pytest.raises(OSError):
            client.tickets.update(first.ticket_id,TicketUpdate(status='RESOLVED',resolution_note='Confirmed'))
    assert read_events(client)==[]
    client.tickets.update(first.ticket_id,TicketUpdate(status='RESOLVED',resolution_note='Confirmed'))
    client.tickets.update(first.ticket_id,TicketUpdate(status='RESOLVED',resolution_note='Extra note'))
    summary=history_summary(client,rows(client))
    assert summary['resolved_total']==summary['resolved_this_week']==1
    assert len(summary['recent'])==1 and summary['recent'][0]['evidence']


def test_one_next_step_dependencies_and_no_implicit_urgency(container):
    client=container.client('acme')
    first=create(client)
    other=create(client,'Compute')
    tickets={t['ticket_id']:t for t in rows(client)}
    actions=[action_summary(t,tickets) for t in tickets.values()]
    actions[1].update(ready=False,blocked_by=[first.ticket_id])
    value=progress(client,actions,[])
    assert value['next_action']['ticket_id']==first.ticket_id
    assert attention(tickets[first.ticket_id])['kind']=='new'
    client.tickets.update(other.ticket_id,TicketUpdate(status='MONITORING',resolution_note='Waiting for data'))
    assert attention(rows(client)[1])['kind']=='waiting'
    waiting=progress(client,[],[dict(status='pending_data',review_after='2099-01-01')])
    assert waiting['next_action'] is None and waiting['waiting_for'] and waiting['review_after'] is None


def test_waiting_for_confirmation_remains_attention_without_marking_every_task(container):
    from finops_agent.chat.read_receipts import needs_attention
    client=container.client('acme')
    ticket=create(client)
    assert not needs_attention(client,dict(status='idle'),[ticket.ticket_id])
    assert needs_attention(client,dict(status='waiting'),[ticket.ticket_id])


def test_consulting_api_exposes_progress_and_guards_adjustment(container):
    from fastapi.testclient import TestClient
    from finops_agent.api.server import app
    from finops_agent.api.routes import get_container
    create(container.client('acme'))
    app.dependency_overrides[get_container]=lambda:container
    try:
        http=TestClient(app)
        response=http.get('/api/v1/clients/acme/consulting')
        assert response.status_code==200
        value=response.json()['agenda']['progress']
        assert value['objective']['total']>=1
        assert value['next_action']['ticket_id']
        goal=value['objective']['id']
        invalid=http.post('/api/v1/clients/acme/consulting/progress/'+goal+'/exclude',
                          json=dict(ticket_id='FIN-999',version=1))
        assert invalid.status_code==409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('change,expected',[
    ({},True),({'context_revision':'stale'},False),({'daily':[{'day':'2026-10-01'}]},False),
    ({'actual':110},False),({'evidence':[]},False),({'period':{'start':'2026-09-01'}},False)])
def test_urgency_requires_material_current_measurement_and_confirmed_policy(container,change,expected):
    from datetime import date
    from finops_agent.consulting.progress_risk import budget_risk
    analysis=dict(status='completed',context_revision='current',run_id='run',period=dict(start='2026-10-01'),
        evidence=[dict(query_id='measured',status='completed')],
        overview=dict(actual=130,billing_currency='USD',daily=[dict(day='2026-10-27')]))
    for key,value in change.items():
        if key in ('actual','daily'):
            analysis['overview'][key]=value
        else:
            analysis[key]=value
    context=dict(revision='current',values=dict(monthly_budget=100,data_latency_days=1,source_cadence_days=1))
    result=budget_risk(analysis,context,container.client('acme').profile,date(2026,10,28))
    assert bool(result)==expected
