from unittest.mock import patch
import httpx
import pytest
from finops_agent.agents.nvidia import NvidiaProvider


@pytest.mark.asyncio
async def test_request_and_safe_response():
    captured = {}
    async def post(self, url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json=dict(choices=[dict(finish_reason='tool_calls', message=dict(
            role='assistant', content=None, reasoning_content='PRIVATE',
            tool_calls=[dict(id='call', type='function', function=dict(name='read_scripts', arguments='{}'))]))],
            usage={'total_tokens': 12}))
    with patch('finops_agent.agents.nvidia.settings', return_value={'NVIDIA_API_KEY': 'fixture-secret'}):
        with patch.object(httpx.AsyncClient, 'post', post):
            result = await NvidiaProvider().complete([dict(role='user', content='test')], [])
    assert captured['url'] == 'https://integrate.api.nvidia.com/v1/chat/completions'
    assert captured['json']['model'] == 'z-ai/glm-5.3-flash'
    assert captured['json']['temperature'] == .5
    assert 'PRIVATE' not in str(result)
    assert 'fixture-secret' not in str(result)
    assert result['message']['tool_calls'][0]['id'] == 'call'


@pytest.mark.asyncio
@pytest.mark.parametrize('status,finish,expected', [(401,'stop','HTTP 401'), (404,'stop','HTTP 404'),
                                                 (200,'length','max_tokens')])
async def test_provider_errors_fail_without_fallback(status, finish, expected):
    async def post(self, url, **kwargs):
        return httpx.Response(status, json=dict(choices=[dict(finish_reason=finish,
                                    message={'role':'assistant','content':'incomplete'})]))
    with patch('finops_agent.agents.nvidia.settings', return_value={'NVIDIA_API_KEY': 'test-key'}):
        with patch.object(httpx.AsyncClient, 'post', post):
            with pytest.raises(ValueError, match=expected):
                await NvidiaProvider().complete([], [])
