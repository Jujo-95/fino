"""Assemble OpenAI-compatible SSE without exposing private reasoning or executing partial tools."""
import json
from typing import Any
import httpx
from .provider_errors import http_failure, transport_failure
from .provider_policy import ProviderPolicy


def apply_delta(message: dict[str, Any], delta: dict[str, Any], calls: dict[int, Any]) -> str:
    text = delta.get('content') or ''
    message['content'] += text
    for piece in delta.get('tool_calls', []):
        call = calls.setdefault(piece['index'], dict(id='',type='function',function=dict(name='',arguments='')))
        if piece.get('id'):
            call['id'] += piece['id']
        for key in ('name','arguments'):
            call['function'][key] += piece.get('function', {}).get(key) or ''
    return str(text)


async def consume_stream(response: Any, on_text: Any, provider: str = 'NVIDIA') -> dict[str, Any]:
    message: dict[str, Any] = dict(role='assistant',content='')
    calls: dict[int, Any] = {}
    usage: dict[str, Any] = {}
    finish = None
    async for line in response.aiter_lines():
        if not line.startswith('data:'):
            continue
        raw = line[5:].strip()
        if raw == '[DONE]':
            break
        chunk = json.loads(raw)
        if chunk.get('error'):
            raise ValueError(f'{provider} interrumpió la respuesta en streaming.')
        usage = chunk.get('usage') or usage
        if not chunk.get('choices'):
            continue
        choice = chunk['choices'][0]
        text = apply_delta(message,choice.get('delta', {}),calls)
        if text:
            await on_text(text)
        finish = choice.get('finish_reason') or finish
    if finish not in ('stop','tool_calls'):
        raise ValueError(f'La respuesta {provider} quedó incompleta; no se ejecutaron herramientas parciales.')
    if calls:
        message['tool_calls'] = [calls[key] for key in sorted(calls)]
    return dict(message=message,usage=usage,finish_reason=finish)


def safe_message(key: str) -> dict[str, str]:
    return {'Authorization':'Bearer '+key}


async def stream_once(key: str, body: dict[str, Any], on_text: Any, read_timeout: float) -> dict[str, Any]:
    partial = False
    async def publish(text: str) -> None:
        nonlocal partial
        partial = True
        await on_text(text)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(read_timeout,connect=10,write=20,pool=10)) as client:
            async with client.stream('POST','https://integrate.api.nvidia.com/v1/chat/completions',
                                     headers=safe_message(key),json=body) as response:
                if response.is_error:
                    raise http_failure(response)
                return await consume_stream(response,publish)
    except httpx.HTTPError as error:
        raise transport_failure(error,partial and not getattr(on_text,'retry_partial',False)) from None


async def stream_completion(key: str, body: dict[str, Any], on_text: Any,
                            policy: ProviderPolicy | None = None) -> dict[str, Any]:
    if policy is None:
        policy = ProviderPolicy({})
    return dict(await policy.run(lambda:stream_once(key,body,on_text,policy.read_timeout)))
