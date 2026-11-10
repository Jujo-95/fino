import json
from unittest.mock import patch
import pytest
import httpx
from groq import RateLimitError,AuthenticationError,APIConnectionError
from groq.types.chat import ChatCompletionChunk
from finops_agent.agents.groq_provider import GroqProvider,SDKStream,groq_failure
from finops_agent.agents.nvidia_stream import consume_stream
from finops_agent.agents.provider_errors import ProviderError
from finops_agent.agents import provider_selection,runtime_config
from finops_agent.agents.providers import LLMProviderFactory
from finops_agent.agents.nvidia import settings
from test_runtime_provider import runtime_env


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(provider_selection,'_session',{})


@pytest.mark.asyncio
async def test_groq_payload_native_tools_and_cross_provider_history(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','gsk_fixture_key')
    p=GroqProvider()
    class Limiter:
        async def aacquire(self):return True
    p.policy.limiter=Limiter()
    captured={}
    async def request(key,body,on_text):
        captured.update(body)
        assert key=='gsk_fixture_key'
        return dict(message=dict(role='assistant',content='OK'),usage={})
    async def publish(text):pass
    with patch.object(p,'request',request):
        await p.stream_complete([dict(role='user',content='Test',provider_content={'private':'Gemini signature'})],
            [dict(type='function',function=dict(name='test',parameters={'type':'object','properties':{}}))],publish,128)
    assert captured['model']=='openai/gpt-oss-20b' and captured['max_completion_tokens']==128
    assert captured['tool_choice']=='auto' and not captured['parallel_tool_calls']
    assert not captured['include_reasoning'] and 'provider_content' not in captured['messages'][0]
    assert 'reasoning_effort' not in captured


@pytest.mark.asyncio
async def test_sdk_chunks_reuse_stream_parser_without_private_reasoning():
    async def sdk_stream():
        for choices,extra in [([dict(index=0,delta={'reasoning':'private reasoning'},finish_reason=None)],{}),
                ([dict(index=0,delta={'tool_calls':[dict(index=0,id='call-1',type='function',function={'name':'query_finance','arguments':'{"sql":'})]},finish_reason=None)],{}),
                ([dict(index=0,delta={'tool_calls':[dict(index=0,function={'arguments':'"SELECT 1"}'})]},finish_reason='tool_calls')],{'x_groq':{'usage':{'total_tokens':10,'prompt_tokens':6,'completion_tokens':4}}})]:
            yield ChatCompletionChunk.model_validate(dict(id='test',object='chat.completion.chunk',created=1,model='openai/gpt-oss-20b',choices=choices,**extra))
    seen=[]
    async def publish(text):seen.append(text)
    result=await consume_stream(SDKStream(sdk_stream()),publish,provider='Groq')
    assert not seen and 'private reasoning' not in json.dumps(result)
    assert result['usage']['total_tokens']==10
    assert json.loads(result['message']['tool_calls'][0]['function']['arguments'])=={'sql':'SELECT 1'}


def test_provider_errors_hide_secrets_and_honor_retry_after():
    request=httpx.Request('POST','https://api.groq.com/openai/v1/chat/completions')
    for error,expected in [(RateLimitError('private raw key',response=httpx.Response(429,request=request,headers={'retry-after':'45'}),body={}),45),
            (AuthenticationError('private raw key',response=httpx.Response(401,request=request),body={}),0)]:
        safe=groq_failure(error,False)
        assert safe.retry_after==expected and 'private' not in str(safe) and 'Groq' in str(safe)
        assert not groq_failure(error,True).retryable
    assert groq_failure(APIConnectionError(request=request),False).retryable


@pytest.mark.asyncio
async def test_missing_key_is_explicit_without_external_call(monkeypatch):
    with patch('finops_agent.agents.groq_provider.settings',return_value={}):
        p=GroqProvider()
        async def publish(text):pass
        with pytest.raises(ProviderError,match='Groq'):
            await p.stream_complete([],[],publish)


def test_groq_selection_retains_other_credentials_and_restart(runtime_env,container,monkeypatch):
    http,vault=runtime_env
    headers={'X-Finops-Config':'1'}
    body=dict(provider='groq',model='openai/gpt-oss-20b',api_key='gsk_fixture_secret')
    result=http.put('/api/v1/runtime/provider',headers=headers,json=body)
    assert result.status_code==200,result.text
    assert isinstance(container.llm,GroqProvider) and 'gsk_fixture_secret' not in result.text
    assert settings('groq')['GROQ_API_KEY']=='gsk_fixture_secret'
    assert 'GROQ_API_KEY' not in settings('gemini') or settings('gemini')['GROQ_API_KEY']!='gsk_fixture_secret'
    assert 'gsk_fixture_secret' not in runtime_config.PATH.with_name('provider.json').read_text()
    public=http.get('/api/v1/runtime/providers').json()
    groq=next(p for p in public['providers'] if p['id']=='groq')
    assert public['active']=='groq' and groq['configured'] and 'openai/gpt-oss-120b' in groq['model_options']
    monkeypatch.setenv('FINOPS_LLM_PROVIDER','groq')
    provider_selection._session.clear()
    runtime_config.load()
    assert isinstance(LLMProviderFactory.create(),GroqProvider)
    assert settings('groq')['GROQ_API_KEY']=='gsk_fixture_secret'


@pytest.mark.asyncio
async def test_official_sdk_request_disables_internal_retries_and_parses_sse():
    from groq import AsyncGroq as OfficialClient
    captured=[]
    def handle(request):
        captured.append(json.loads(request.content))
        assert request.headers['authorization']=='Bearer gsk_fixture_secret'
        chunk=dict(id='fixture',object='chat.completion.chunk',created=1,model='openai/gpt-oss-20b',
            choices=[dict(index=0,delta={'content':'Ready'},finish_reason='stop')])
        return httpx.Response(200,headers={'content-type':'text/event-stream'},text='data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n')
    def client(**kwargs):
        assert kwargs['max_retries']==0
        return OfficialClient(**kwargs,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    p=GroqProvider()
    seen=[]
    async def publish(text):seen.append(text)
    with patch('finops_agent.agents.groq_provider.AsyncGroq',client):
        result=await p.request('gsk_fixture_secret',dict(model=p.model,messages=[dict(role='user',content='Test')],stream=True),publish)
    assert result['message']['content']=='Ready' and seen==['Ready']
    assert len(captured)==1 and p.verified_at is not None


def test_groq_session_only_key_never_reaches_vault_or_disk(runtime_env):
    http,vault=runtime_env
    response=http.put('/api/v1/runtime/provider',headers={'X-Finops-Config':'1'},json=dict(
        provider='groq',model='openai/gpt-oss-20b',api_key='gsk_session_secret',persist_key=False))
    assert response.status_code==200,response.text
    assert not vault and settings('groq')['GROQ_API_KEY']=='gsk_session_secret'
    assert 'gsk_session_secret' not in response.text
    assert 'gsk_session_secret' not in runtime_config.PATH.with_name('provider.json').read_text()
