import asyncio
import pytest
from finops_agent.agents import runtime_config,provider_selection
from finops_agent.agents.nvidia import settings,NvidiaProvider
from finops_agent.agents.gemini import GeminiProvider
from finops_agent.agents.providers import LLMProviderFactory
from test_runtime_provider import runtime_env

HEADERS={'X-Finops-Config':'1'}


@pytest.fixture(autouse=True)
def isolated_selection(monkeypatch):
    monkeypatch.setattr(provider_selection,'_session',{})


def test_switch_back_and_forth_preserves_keys_models_and_restart(runtime_env,container,monkeypatch):
    http,vault=runtime_env
    nvidia=dict(provider='nvidia',model='nvidia/previous',api_key='fixture-nvidia-secret')
    gemini=dict(provider='gemini',model='gemini-3.6-flash',project='fixture-project',api_key='fixture-gemini-secret')
    assert http.put('/api/v1/runtime/provider',headers=HEADERS,json=nvidia).status_code==200
    initial=container.llm
    assert http.put('/api/v1/runtime/provider',headers=HEADERS,json=gemini).status_code==200
    assert isinstance(container.llm,GeminiProvider)
    assert settings('gemini')['GOOGLE_API_KEY']=='fixture-gemini-secret'
    assert settings('nvidia')['NVIDIA_API_KEY']=='fixture-nvidia-secret'
    public=http.get('/api/v1/runtime/providers')
    assert public.json()['active']=='gemini'
    assert all(p['configured'] for p in public.json()['providers'] if p['id']!='groq')
    assert 'fixture-nvidia-secret' not in public.text and 'fixture-gemini-secret' not in public.text
    del nvidia['api_key']
    assert http.put('/api/v1/runtime/provider',headers=HEADERS,json=nvidia).status_code==200
    assert container.llm is initial and container.llm.model=='nvidia/previous'
    document=runtime_config.PATH.with_name('provider.json').read_text()
    assert 'secret' not in document and 'gemini-3.6-flash' in document
    monkeypatch.setenv('FINOPS_LLM_PROVIDER','nvidia')
    monkeypatch.setattr(runtime_config,'_values',{})
    provider_selection._session.clear()
    runtime_config.load()
    assert isinstance(LLMProviderFactory.create(),NvidiaProvider)
    assert settings('nvidia')['NVIDIA_API_KEY']=='fixture-nvidia-secret'
    assert settings('gemini')['GOOGLE_API_KEY']=='fixture-gemini-secret'
    assert http.get('/api/v1/runtime/providers').json()['providers'][1]['model']=='gemini-3.6-flash'


@pytest.mark.asyncio
async def test_switch_during_active_job_changes_nothing(runtime_env,container):
    from finops_agent.api.provider_switch import switch_provider
    from finops_agent.agents.provider_selection import SelectionUpdate
    from fastapi import HTTPException
    task=asyncio.create_task(asyncio.Event().wait())
    container.chat.tasks['fixture']=task
    try:
        with pytest.raises(HTTPException) as error:
            switch_provider(container,SelectionUpdate(provider='gemini',model='gemini-3.6-flash',project='fixture-project'))
        assert error.value.status_code==409 and not runtime_config.PATH.with_name('provider.json').exists()
    finally:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        container.chat.tasks.clear()


def test_cross_provider_history_preserves_tools_without_foreign_metadata():
    from finops_agent.agents.gemini_messages import contents
    messages=[dict(role='assistant',content='',tool_calls=[dict(id='call',function=dict(name='list_tickets',arguments='{}'))]),
        dict(role='tool',tool_call_id='call',content='{"tickets":[]}')]
    native=contents(messages)
    assert native[0].parts[0].function_call.name=='list_tickets'
    assert native[0].parts[0].thought_signature==b'skip_thought_signature_validator'
    from unittest.mock import patch
    with patch('finops_agent.agents.nvidia.settings',return_value={}):
        provider=NvidiaProvider()
        body=provider.payload([{**messages[0],'provider_content':{'role':'model','parts':[]}}],[])
    assert 'provider_content' not in body['messages'][0]
