import asyncio
import json
from uuid import uuid4
import pytest
from finops_agent.agents.nvidia_stream import consume_stream
from finops_agent.chat.store import ChatStore
from finops_agent.chat.models import ChatMessage


class Response:
    def __init__(self,chunks):
        self.chunks = chunks

    async def aiter_lines(self):
        for chunk in self.chunks:
            yield 'data: '+json.dumps(chunk)
        yield 'data: [DONE]'


def chunk(delta,finish=None):
    return dict(choices=[dict(delta=delta,finish_reason=finish)])


@pytest.mark.asyncio
async def test_content_stream_and_fragmented_tools_never_expose_private_reasoning():
    text = []
    async def receive(value):
        text.append(value)
    pieces = [chunk(dict(reasoning_content='private text')),chunk(dict(content='Hola ')),chunk(dict(content='mundo')),
        chunk(dict(tool_calls=[dict(index=0,id='call-1',function=dict(name='get_',arguments='{"ticket_'))])),
        chunk(dict(tool_calls=[dict(index=0,function=dict(name='tickets',arguments='ids":["FIN-001"]}'))]),'tool_calls')]
    result = await consume_stream(Response(pieces),receive)
    assert text == ['Hola ','mundo']
    assert 'private text' not in str(result)
    call = result['message']['tool_calls'][0]
    assert call['function']['name']=='get_tickets'
    assert json.loads(call['function']['arguments'])==dict(ticket_ids=['FIN-001'])


@pytest.mark.asyncio
@pytest.mark.parametrize('finish',[None,'length'])
async def test_incomplete_stream_does_not_release_partial_tools(finish):
    async def receive(value):
        pass
    with pytest.raises(ValueError,match='incompleta'):
        await consume_stream(Response([chunk(dict(tool_calls=[dict(index=0,id='partial',function=dict(name='plan_ticket_changes',arguments='{'))]),finish)]),receive)


@pytest.mark.asyncio
async def test_live_text_is_visible_before_graph_finishes_and_committed_once(container):
    started,release = asyncio.Event(),asyncio.Event()
    class StreamingModel:
        model = 'explicit-stream-test-double'
        async def complete(self,*args):
            raise AssertionError('The chat must use streaming when available')
        async def stream_complete(self,messages,tools,on_text):
            await on_text('Respuesta ')
            started.set()
            await release.wait()
            await on_text('completa.')
            return dict(message=dict(role='assistant',content='Respuesta completa.'),usage={})
    container.llm = StreamingModel()
    store = ChatStore(container.client('acme'))
    thread = store.create()
    container.chat.start('acme',thread['thread_id'],ChatMessage(text='Hola',message_id=uuid4().hex))
    task = container.chat.tasks['acme:'+thread['thread_id']]
    await asyncio.wait_for(started.wait(),5)
    during = store.read(thread['thread_id'])
    assert during['status']=='running'
    assert during['streaming']['content']=='Respuesta '
    release.set()
    await task
    final = store.read(thread['thread_id'])
    assert final['status']=='ready'
    assert final['streaming'] is None
    assert [m['content'] for m in final['messages'] if m['role']=='ai']==['Respuesta completa.']
