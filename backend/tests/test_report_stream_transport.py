from contextlib import asynccontextmanager
from unittest.mock import patch
import httpx
import pytest
from finops_agent.agents.nvidia import NvidiaProvider
from finops_agent.agents.nvidia_stream import stream_once
from finops_agent.agents.provider_errors import ProviderError


@pytest.mark.asyncio
@pytest.mark.parametrize('emitted,internal,expected',[(False,False,'read_timeout'),(True,False,'stream_interrupted'),(True,True,'read_timeout')])
async def test_headers_do_not_count_as_partial_user_output(emitted,internal,expected):
    class Response:
        is_error=False
        async def aiter_lines(self):
            if emitted:
                yield 'data: {"choices":[{"delta":{"content":"draft"}}]}'
            raise httpx.ReadTimeout('private request')
    @asynccontextmanager
    async def stream(*args,**kwargs):
        yield Response()
    async def receive(text):
        pass
    setattr(receive,'retry_partial',internal)
    with patch.object(httpx.AsyncClient,'stream',stream):
        with pytest.raises(ProviderError) as raised:
            await stream_once('fixture-key',{},receive,90)
    assert raised.value.code==expected


@pytest.mark.asyncio
async def test_reports_use_streaming_and_do_not_publish_draft():
    captured={}
    async def request(key,body,on_text):
        captured.update(body)
        assert getattr(on_text,'retry_partial',False)
        await on_text('internal draft')
        return dict(message=dict(role='assistant',content='Final result'),usage={})
    with patch('finops_agent.agents.nvidia.settings',return_value=dict(NVIDIA_API_KEY='fixture-key')):
        provider=NvidiaProvider()
        provider.transport.request=request
        result=await provider.complete_for_report([dict(role='user',content='Test')],[],max_tokens=128)
    assert captured['stream'] and captured['max_tokens']==128
    assert result['message']['content']=='Final result'
