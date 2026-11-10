import asyncio
from unittest.mock import patch
import pytest
from google.genai import types
from langchain_core.messages import AIMessage,ToolMessage
from finops_agent.agents.gemini import GeminiProvider,collect,failure
from finops_agent.agents.gemini_messages import contents,generation_config,result_message
from finops_agent.agents.providers import LLMProviderFactory
from finops_agent.agents.provider_errors import ProviderError
from finops_agent.chat.provider_messages import provider_messages


@pytest.fixture(autouse=True)
def isolated_preferences(monkeypatch):
    from finops_agent.agents import provider_selection
    monkeypatch.setattr(provider_selection,'saved',lambda:{})
    monkeypatch.setattr(provider_selection,'_session',{})


def test_provider_factory_and_native_schema(monkeypatch):
    monkeypatch.setenv('FINOPS_LLM_PROVIDER','gemini')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','fixture-project')
    monkeypatch.setenv('GEMINI_MODEL','gemini-3.6-flash')
    p=LLMProviderFactory.create()
    assert isinstance(p,GeminiProvider) and p.native_tools
    assert p.readiness()['project']=='fixture-project'
    assert 'GOOGLE_API_KEY' not in p.audit_config()
    from finops_agent.chat.models import PlanRequest
    config=generation_config([dict(role='system',content='Tenant isolated')],[dict(function=dict(
        name='plan_ticket_changes',parameters=PlanRequest.model_json_schema()))],4096)
    assert config.tools[0].function_declarations[0].parameters_json_schema['$defs']['Change']
    assert config.automatic_function_calling.disable


def test_checkpoint_roundtrip_preserves_opaque_signatures_and_hides_thoughts():
    result=result_message([types.Part(text='Private thought',thought=True),types.Part(text='Visible explanation'),
        types.Part(function_call=types.FunctionCall(name='query_finance',args={'sql':'SELECT 1'}),thought_signature=b'\xff\x01\x80')])
    assert 'Private thought' not in str(result)
    call=result['tool_calls'][0]
    ai=AIMessage(content=result['content'],tool_calls=[dict(id=call['id'],name='query_finance',args={'sql':'SELECT 1'})],
        additional_kwargs={'provider_content':result['provider_content']})
    stored=AIMessage.model_validate_json(ai.model_dump_json())
    native=contents(provider_messages([stored,ToolMessage(content='{"rows":[1]}',tool_call_id=call['id'],name='query_finance')]))
    assert native[0].parts[-1].thought_signature==b'\xff\x01\x80'
    assert native[-1].parts[0].function_response.name=='query_finance'
    assert native[-1].parts[0].function_response.id==call['id']


@pytest.mark.asyncio
async def test_stream_outputs_text_in_order_and_waits_for_completed_tools():
    async def stream():
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[types.Part(text='Primero ')]))])
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[types.Part(text='después')]),finish_reason='STOP')])
    seen=[]
    async def publish(text):seen.append(text)
    result=await collect(stream(),publish)
    assert seen==['Primero ','después'] and result['message']['content']=='Primero después'
    async def incomplete():
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[
            types.Part(function_call=types.FunctionCall(name='plan_ticket_changes',args={}))]),finish_reason='MAX_TOKENS')])
    with pytest.raises(ProviderError,match='incompleta'):
        await collect(incomplete(),publish)


def test_gemini_errors_and_shared_limits_do_not_claim_nvidia():
    from types import SimpleNamespace
    for status in (400,401,403,404,429,500):
        error=failure(SimpleNamespace(code=status),False)
        assert 'Gemini' in str(error) and 'NVIDIA' not in str(error)
        assert error.retryable==(status in (429,500))
    assert not failure(SimpleNamespace(code=500),True).retryable
    p=GeminiProvider()
    p.policy.blocked_until=float('inf')
    with pytest.raises(ProviderError,match='Gemini'):
        p.policy.check()


@pytest.mark.parametrize('emitted',[False,True])
def test_billing_disabled_is_actionable_and_never_retried(emitted):
    from google.genai.errors import ClientError
    raw=ClientError(403,{'error':{'message':'Secret upstream details','details':[
        {'reason':'BILLING_DISABLED','metadata':{'consumer':'private-project'}}]}})
    result=failure(raw,emitted)
    assert result.code=='billing_disabled' and not result.retryable
    assert 'facturación deshabilitada' in str(result)
    assert 'Secret' not in str(result) and 'private-project' not in str(result)


@pytest.mark.asyncio
async def test_cancellation_propagates_and_releases_shared_slots(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY','fixture-key')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','fixture-project')
    p=GeminiProvider()
    class Limiter:
        async def aacquire(self):return True
    p.policy.limiter=Limiter()
    started=asyncio.Event()
    async def request(*args):
        started.set()
        await asyncio.Event().wait()
    async def publish(text):pass
    with patch.object(p,'request',request):
        task=asyncio.create_task(p.stream_complete([dict(role='user',content='Test')],[],publish))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert p.policy.pending==0 and not p.policy.slots.locked()


def test_runtime_nvidia_preferences_do_not_override_gemini(monkeypatch):
    from finops_agent.agents.nvidia import settings
    monkeypatch.setenv('FINOPS_LLM_PROVIDER','gemini')
    monkeypatch.setenv('FINOPS_LLM_MODEL','fixture-gemini')
    with patch('finops_agent.agents.runtime_config.overrides',return_value={'FINOPS_LLM_MODEL':'nvidia-old','NVIDIA_API_KEY':'private'}):
        assert settings()['FINOPS_LLM_MODEL']=='fixture-gemini'
