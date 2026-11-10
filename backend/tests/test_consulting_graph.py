import json
from uuid import uuid4
import pytest
from finops_agent.agents_v2.registry import ORCHESTRATOR
from finops_agent.chat.models import ChatMessage
from finops_agent.chat.store import ChatStore
from finops_agent.consulting.store import ConsultingStore
from test_chat_graph import wait_job


def call(name, args):
    return dict(message=dict(role='assistant',content='',tool_calls=[dict(id=uuid4().hex,type='function',
        function=dict(name=name,arguments=json.dumps(args)))]))


class ConsultantDouble:
    async def complete(self,messages,tools):
        names = {t['function']['name'] for t in tools}
        assert 'read_diagnosis' in names and 'propose_context_changes' in names
        last = messages[-1]
        if last['role']=='user':
            return call('read_diagnosis', {})
        data = json.loads(last['content'])
        if last.get('name')=='read_diagnosis':
            assert not data['context']['values']
            return call('propose_context_changes', dict(expected_revision=data['context']['revision'],
                values=dict(monthly_budget=42000), reason='El usuario confirmó su presupuesto en el mensaje.'))
        assert data['status']=='pending'
        return dict(message=dict(role='assistant',content='Revisa y confirma el presupuesto en la propuesta.'))


@pytest.mark.asyncio
async def test_v2_graph_reads_diagnosis_proposes_context_and_requires_confirmation(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme', csv_path)
    store = ChatStore(client)
    thread = store.create(ORCHESTRATOR)
    container.llm = ConsultantDouble()
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Mi presupuesto aprobado es 42000 USD.',message_id=uuid4().hex))
    ready = await wait_job(container,thread)
    assert ready['status']=='ready',ready.get('error')
    proposal = next(a['result'] for a in ready['activity'] if a['tool']=='propose_context_changes')
    assert ConsultingStore(client).context()['values']=={}
    ConsultingStore(client).decide(proposal['proposal_id'], 'confirm', uuid4().hex)
    assert ConsultingStore(client).context()['values']['monthly_budget']==42000
    assert not client.tickets.list()
