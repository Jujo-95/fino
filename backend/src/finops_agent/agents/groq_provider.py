"""Groq official SDK adapter with shared limits and audited local tool execution."""
import json
from datetime import datetime,timezone
from typing import Any
import httpx
from groq import AsyncGroq,APIError,APIStatusError
from .nvidia import settings
from .nvidia_stream import consume_stream
from .provider_policy import ProviderPolicy
from .provider_errors import ProviderError,retry_delay

DEFAULT_MODEL = 'openai/gpt-oss-20b'
MODEL_OPTIONS = ['openai/gpt-oss-20b','openai/gpt-oss-120b','qwen/qwen3.8-27b']


class GroqProvider:
    native_tools = True

    def __init__(self) -> None:
        config = settings('groq')
        self.model = config.get('GROQ_MODEL',DEFAULT_MODEL)
        self.policy = ProviderPolicy(config,provider='Groq')
        self.verified_at: str | None = None

    def readiness(self) -> dict[str,Any]:
        return dict(provider='Groq',model=self.model,configured=bool(settings('groq').get('GROQ_API_KEY')),
            mode='llm_agent',verified_at_utc=self.verified_at,base_url='https://api.groq.com/openai/v1',
            limits=self.policy.public(),fallback_model=None,credential_source='environment_or_keychain')

    def audit_config(self) -> dict[str,Any]:
        return dict(provider='Groq',model=self.model,temperature=.5,stream=True,
            max_tokens=int(settings('groq').get('GROQ_MAX_TOKENS','4096')))

    async def complete(self, messages: list[dict[str,Any]], tools: list[dict[str,Any]]) -> dict[str,Any]:
        return await self.complete_for_report(messages,tools)

    async def complete_for_report(self, messages: list[dict[str,Any]], tools: list[dict[str,Any]], max_tokens: int | None = None) -> dict[str,Any]:
        async def discard(_text: str) -> None:
            pass
        return await self.stream_complete(messages,tools,discard,max_tokens)

    async def stream_complete(self, messages: list[dict[str,Any]], tools: list[dict[str,Any]], on_text: Any, max_tokens: int | None = None) -> dict[str,Any]:
        config = settings('groq')
        key = config.get('GROQ_API_KEY','')
        if not key:
            raise ProviderError('invalid_credentials','Configura tu API key de Groq en Conexión IA.')
        self.policy.bind_key(key)
        body: dict[str,Any] = dict(model=self.model,messages=[{k:v for k,v in m.items() if k!='provider_content'} for m in messages],
            temperature=.5,max_completion_tokens=max_tokens or int(config.get('GROQ_MAX_TOKENS','4096')),stream=True)
        if tools:
            body.update(tools=tools,tool_choice='auto',parallel_tool_calls=False)
        if self.model.startswith('openai/gpt-oss'):
            body['include_reasoning'] = False
        return dict(await self.policy.run(lambda:self.request(key,body,on_text)))

    async def request(self, key: str, body: dict[str,Any], on_text: Any) -> dict[str,Any]:
        emitted = False
        async def publish(text: str) -> None:
            nonlocal emitted
            emitted = True
            await on_text(text)
        try:
            async with AsyncGroq(api_key=key,max_retries=0,
                    timeout=httpx.Timeout(self.policy.read_timeout,connect=10,write=20,pool=10)) as client:
                stream = await client.chat.completions.create(**body)
                result = await consume_stream(SDKStream(stream),publish,provider='Groq')
            self.verified_at = datetime.now(timezone.utc).isoformat()
            return {**result,'model':self.model,'requested_model':self.model,'fallback':False}
        except APIError as error:
            raise groq_failure(error,emitted) from None


class SDKStream:
    def __init__(self, stream: Any) -> None:
        self.stream = stream

    async def aiter_lines(self) -> Any:
        async for chunk in self.stream:
            data = chunk.model_dump(exclude_none=True)
            if not data.get('usage') and isinstance(data.get('x_groq'),dict):
                data['usage'] = data['x_groq'].get('usage',{})
            yield 'data: '+json.dumps(data)


def groq_failure(error: APIError, emitted: bool) -> ProviderError:
    status = error.status_code if isinstance(error,APIStatusError) else None
    code = {400:'invalid_request',401:'invalid_credentials',403:'access_denied',404:'model_not_found',
        413:'request_too_large',429:'provider_rate_limit'}.get(status or 0,'provider_unavailable' if status else 'connection_error')
    labels = {400:'revisa el modelo y el formato de las herramientas',401:'la API key fue rechazada',
        403:'la cuenta no tiene acceso al modelo',404:'el modelo no está disponible',413:'el contexto excede el límite de la cuenta',
        429:'se alcanzó una cuota de Groq; espera antes de reintentar'}
    message = f'Groq HTTP {status}: {labels.get(status or 0,"servicio no disponible temporalmente")}.' if status else 'No se pudo conectar con Groq.'
    delay = retry_delay(error.response.headers.get('retry-after')) if isinstance(error,APIStatusError) else 0
    return ProviderError('stream_interrupted' if emitted else code,message,
        not emitted and (status is None or status in (408,429,500,502,503,504)),delay)
