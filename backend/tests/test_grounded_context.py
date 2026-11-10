"""Persistence truth comes from backend reads, including across conversations."""
from uuid import uuid4
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.chat.grounding import verified_state
from finops_agent.chat.store import ChatStore
from finops_agent.consulting.models import ContextProposal,ContextValues
from finops_agent.consulting.store import ConsultingStore
from finops_agent.consulting.receipts import confirmation_receipt
from finops_agent.consulting.workflow import sync_tasks

OWNERS={'ml-platform':'data-platform','prod-payments':'app','shared-network':'app'}


def test_confirmation_receipt_and_new_thread_read_durable_truth(container,csv_path):
    client=container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    sync_tasks(client)
    ticket=next(t for t in client.tickets.list() if t.workflow_key=='requirement:owners')
    context=ConsultingStore(client)
    proposal=context.propose(ContextProposal(expected_revision=context.context()['revision'],
        values=ContextValues(owners=OWNERS),reason='Explicit test assignment'),'test')
    command=uuid4().hex
    receipt=confirmation_receipt(client,context.decide(proposal['proposal_id'],'confirm',command),command)['receipt']
    assert receipt['persisted'] and receipt['values']=={'owners':OWNERS}
    assert {'ticket_id':ticket.ticket_id,'status':'IMPLEMENTED'} in receipt['tickets']
    store=ChatStore(client)
    fresh=store.create(ORCHESTRATOR,ticket_id=ticket.ticket_id)
    fresh['turn_id']=uuid4().hex
    store.save(fresh)
    snapshot=verified_state(store,fresh)
    assert snapshot['confirmed_context']['values']['owners']==OWNERS
    assert snapshot['tickets'][0]['status']=='IMPLEMENTED'
    assert store.read(fresh['thread_id'])['activity'][-1]['tool']=='read_confirmed_context'
    assert context.context()['values'].keys()=={'owners'}


def test_failed_read_never_claims_saved_or_missing(container,monkeypatch):
    store=ChatStore(container.client('acme'))
    thread=store.create(ORCHESTRATOR)
    def failed(*args):
        raise RuntimeError('Offline fixture')
    monkeypatch.setattr(ConsultingStore,'context',failed)
    snapshot=verified_state(store,thread)
    assert snapshot['status']=='unavailable' and 'confirmed_context' not in snapshot
    assert store.read(thread['thread_id'])['activity'][-1]['tool']=='verify_backend_state'


def test_context_revision_is_bound_and_concurrent_change_still_rejected(container,csv_path):
    import pytest
    from finops_agent.chat.tools import ToolContext
    from finops_agent.consulting.tools import consulting_tools
    client=container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    sync_tasks(client)
    chat=ChatStore(client)
    thread=chat.create(ORCHESTRATOR)
    thread['turn_id']=uuid4().hex
    chat.save(thread)
    verified_state(chat,thread)
    ctx=ToolContext(container,'acme',thread['thread_id'],thread['turn_id'])
    tool=next(t for t in consulting_tools(ctx) if t.name=='propose_context_changes')
    result=tool.invoke(dict(values={'owners':OWNERS},reason='Explicit user assignment',expected_revision='f'*64))
    context=ConsultingStore(client)
    assert result['expected_revision']==context.context()['revision'] and not context.context()['values']
    competing=context.propose(ContextProposal(expected_revision=context.context()['revision'],
        values=ContextValues(objective='Control financiero'),reason='Concurrent confirmed input'),'other-thread')
    context.decide(competing['proposal_id'],'confirm',uuid4().hex)
    with pytest.raises(ValueError,match='contexto cambió'):
        tool.invoke(dict(values={'owners':OWNERS},reason='Stale model request'))
    assert context.context()['values']=={'objective':'Control financiero'}
