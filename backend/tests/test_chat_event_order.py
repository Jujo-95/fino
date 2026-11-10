import json
from uuid import uuid4
import pytest
from finops_agent.chat.store import ChatStore
from finops_agent.chat.models import ChatMessage
from test_chat_graph import wait_job


@pytest.mark.asyncio
async def test_more_than_eight_rounds_keep_activity_at_its_message(container):
    class Model:
        calls = 0
        async def complete(self,messages,tools):
            self.calls += 1
            message = dict(role='assistant',content=f'Avance {self.calls}')
            if self.calls<=10:
                message['tool_calls'] = [dict(id=uuid4().hex,type='function',
                    function=dict(name='list_tickets',arguments=json.dumps({}))) ]
            return dict(message=message)
    container.llm = Model()
    store = ChatStore(container.client('acme'))
    thread = store.create()
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Analiza',message_id=uuid4().hex))
    result = await wait_job(container,thread)
    assert result['status']=='ready',result.get('error')
    assert container.llm.calls==11
    messages = [m for m in result['messages'] if m['role']=='ai']
    actions = [a for a in result['activity'] if a['tool']=='list_tickets']
    assert len(actions)==10
    assert [a['after_message_id'] for a in actions]==[m['id'] for m in messages[:10]]
    assert store.read(thread['thread_id'])['activity']==result['activity']
