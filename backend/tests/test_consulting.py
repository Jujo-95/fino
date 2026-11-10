from uuid import uuid4
import pytest
from finops_agent.consulting.store import ConsultingStore
from finops_agent.consulting.models import ContextProposal, ContextValues
from finops_agent.consulting.diagnosis import diagnosis
from finops_agent.consulting.agenda import agenda
from finops_agent.models import ClientProfile


def confirm(client, values):
    store = ConsultingStore(client)
    proposal = store.propose(ContextProposal(expected_revision=store.context()['revision'],
        values=ContextValues(**values), reason='Explicit test user confirmation'), 'test')
    store.decide(proposal['proposal_id'], 'confirm', uuid4().hex)
    return store


@pytest.mark.parametrize('loaded', [False, True])
def test_readiness_never_confuses_defaults_and_evidence(container, csv_path, loaded):
    client = container.client('acme')
    if loaded:
        client.engine.ingest_focus_csv('acme', csv_path)
    result = diagnosis(client)
    assert all(c['state']!='NO_ISSUES_DETECTED' for c in result['capabilities'])
    assert 'monthly_budget' in {r['id'] for r in result['requirements']}
    assert not result['context']['values']
    assert diagnosis(client)['revision']==result['revision']
    assert not client.tickets.list()
    assert result['facts']['allocation']['owned_cost_pct'] in (None, 0)


def test_confirmation_is_persistent_idempotent_conflict_checked_and_tenant_scoped(container):
    client = container.client('acme')
    store = ConsultingStore(client)
    body = ContextProposal(expected_revision=store.context()['revision'], values=ContextValues(monthly_budget=45000), reason='Aprobado')
    proposal = store.propose(body, 'test')
    stale = store.propose(body.model_copy(update={'values':ContextValues(objective='Control')}), 'test')
    command = uuid4().hex
    receipt = store.decide(proposal['proposal_id'], 'confirm', command)
    assert store.decide(proposal['proposal_id'], 'confirm', command)==receipt
    assert ConsultingStore(client).context()['values']=={'monthly_budget':45000}
    with pytest.raises(ValueError, match='desactualizada'):
        store.decide(stale['proposal_id'], 'confirm', uuid4().hex)
    other = container.onboard(ClientProfile(client_id='other', client_name='Other'))
    with pytest.raises(KeyError):
        ConsultingStore(other).decide(proposal['proposal_id'], 'confirm', uuid4().hex)
    assert ConsultingStore(other).context()['values']=={}
    assert len(store.context()['history'])==1


def test_weighted_assignment_gaps_and_freshness_are_separate(container, csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    confirm(client, dict(expected_accounts=['prod-payments','missing-account'], owners={'shared-network':'Platform'},
                         source_cadence_days=1, data_latency_days=0))
    with client.engine.atomic_tx() as tx:
        tx.execute("DELETE FROM focus_usage WHERE SubAccountId='prod-payments' AND CAST(ChargePeriodStart AS DATE)='2026-10-03'")
    result = diagnosis(client)
    assert result['facts']['missing_accounts']==['missing-account']
    assert '2026-10-03' in result['facts']['missing_days']['prod-payments']
    allocation = result['facts']['allocation']
    assert 0 < allocation['owned_cost_pct'] < 20
    assert allocation['tagged_cost_pct'] > 70
    assert result['use_case_preflight']
    assert result['facts']['focus_validation']=='internal_checks_only'


def test_agenda_does_not_block_anomaly_on_missing_ownership(container):
    from test_chat_operations import ops
    operations = ops.__wrapped__(container)
    ticket = operations.client.tickets.list()[0]
    changed = ticket.model_copy(update={'capability':'anomaly-management'})
    operations.client.tickets._commit(changed)
    plan = agenda(operations.client)
    assert plan['top_actions'][0]['ticket_id']==ticket.ticket_id
    assert plan['top_actions'][0]['ready']
    assert plan['next_requirement']['id']=='billing'


def test_supplementary_preflight_requires_matching_history_and_import_is_idempotent(container,csv_path):
    from finops_agent.consulting.supporting import SupportingInput, import_supporting
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    payload = dict(source='Cloud monitoring export',evidence_reference='local-monitoring:october',
        utilization=[dict(account='prod-payments',resource_id='Amazon EC2',day=f'2026-10-{d:02d}',
                          cpu_pct=15,memory_pct=25) for d in range(1,8)])
    body = SupportingInput.model_validate(payload)
    first = import_supporting(client,body)
    diagnosis_before = diagnosis(client)
    assert import_supporting(client,body)==first
    assert diagnosis(client)['revision']==diagnosis_before['revision']
    assert 'utilization' not in {r['id'] for r in diagnosis_before['requirements']}
    other = container.onboard(ClientProfile(client_id='other',client_name='Other'))
    assert 'utilization' in {r['id'] for r in diagnosis(other)['requirements']}


def test_acknowledged_idle_days_do_not_remain_missing_partitions(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    with client.engine.atomic_tx() as tx:
        tx.execute("DELETE FROM focus_usage WHERE SubAccountId='prod-payments' AND CAST(ChargePeriodStart AS DATE)='2026-10-03'")
    confirm(client,dict(non_billable_days={'prod-payments':['2026-10-03']}))
    assert not diagnosis(client)['facts']['missing_days']
