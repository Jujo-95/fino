"""Google Gen AI SDK provider; shared limits, tools and no cross-provider fallback."""
from datetime import datetime,timezone
from typing import Any
import httpx
from google import genai
from google.genai import errors,types
from .nvidia import settings
from .provider_policy import ProviderPolicy
from .provider_errors import ProviderError
from .gemini_messages import contents,generation_config,result_message


class GeminiProvider:
    native_tools = True

    def __init__(self) -> None:
        config = settings('gemini')
        self.model = config.get('GEMINI_MODEL','gemini-3.6-flash')
        self.project = config.get('GOOGLE_CLOUD_PROJECT','')
        self.location = config.get('GOOGLE_CLOUD_LOCATION','global')
        self.policy = ProviderPolicy(config,provider='Gemini')
        self.verified_at: str | None = None

    def readiness(self) -> dict[str,Any]:
        return dict(provider='Gemini',model=self.model,project=self.project,location=self.location,
            configured=bool(settings('gemini').get('GOOGLE_API_KEY') and self.project),mode='llm_agent',
            verified_at_utc=self.verified_at,limits=self.policy.public(),fallback_model=None,
            credential_source='environment',secure_storage=False)

    def audit_config(self) -> dict[str,Any]:
        return dict(provider='Gemini',model=self.model,project=self.project,location=self.location,
            temperature=.5,max_tokens=int(settings('gemini').get('FINOPS_MAX_TOKENS','4096')),stream=True)

    async def complete(self, messages: list[dict[str,Any]], tools: list[dict[str,Any]]) -> dict[str,Any]:
        return await self.complete_for_report(messages,tools)

    async def complete_for_report(self, messages: list[dict[str,Any]], tools: list[dict[str,Any]], max_tokens: int | None = None) -> dict[str,Any]:
        async def discard(_text: str) -> None:
            pass
        return await self.stream_complete(messages,tools,discard,max_tokens)

    async def stream_complete(self, messages: list[dict[str,Any]], tools: list[dict[str,Any]], on_text: Any, max_tokens: int | None = None) -> dict[str,Any]:
        config = settings('gemini')
        key = config.get('GOOGLE_API_KEY','')
        if not key or not self.project:
            raise ProviderError('invalid_credentials','Configura GOOGLE_API_KEY y GOOGLE_CLOUD_PROJECT para Gemini.')
        self.policy.bind_key(key)
        maximum = max_tokens or int(config.get('FINOPS_MAX_TOKENS','4096'))
        return dict(await self.policy.run(lambda:self.request(key,messages,tools,on_text,maximum)))

    async def request(self, key: str, messages: list[dict[str,Any]], tools: list[dict[str,Any]], on_text: Any, maximum: int) -> dict[str,Any]:
        emitted = False
        async def publish(text: str) -> None:
            nonlocal emitted
            emitted = True
            await on_text(text)
        try:
            async with genai.Client(enterprise=True,api_key=key,project=self.project,location=self.location,
                    http_options=types.HttpOptions(timeout=int(self.policy.read_timeout*1000),
                        retry_options=types.HttpRetryOptions(attempts=1))).aio as client:
                stream = await client.models.generate_content_stream(model=self.model,contents=contents(messages),
                    config=generation_config(messages,tools,maximum))
                result = await collect(stream,publish)
            self.verified_at = datetime.now(timezone.utc).isoformat()
            return {**result,'model':self.model,'requested_model':self.model,'fallback':False}
        except (errors.APIError,httpx.HTTPError) as error:
            raise failure(error,emitted) from None


def failure(error: Any, emitted: bool) -> ProviderError:
    status = getattr(error,'code',None)
    details = getattr(error,'details',{})
    envelope = details.get('error',details) if isinstance(details,dict) else {}
    reasons = {item.get('reason') for item in envelope.get('details',[]) if isinstance(item,dict)}
    if 'BILLING_DISABLED' in reasons:
        return ProviderError('billing_disabled','Gemini: Google Cloud tiene la facturación deshabilitada en el proyecto configurado. Revisa su cuenta de facturación en Google Cloud; cambiar la API key no resuelve este error.',False)
    code = {400:'invalid_request',401:'invalid_credentials',403:'access_denied',404:'model_not_found',429:'provider_rate_limit'}.get(status or 0,'provider_unavailable')
    retry = status in (408,429,500,502,503,504) or isinstance(error,httpx.HTTPError)
    message = f'Gemini HTTP {status}: revisa modelo, permisos y cuota.' if status else 'No se pudo completar la conexión con Gemini.'
    return ProviderError('stream_interrupted' if emitted else code,message,retry and not emitted,5 if status==429 else 0)


async def collect(stream: Any, publish: Any) -> dict[str,Any]:
    parts,usage,finish = [],{},None
    async for chunk in stream:
        if chunk.usage_metadata:
            usage = chunk.usage_metadata.model_dump(mode='json',exclude_none=True)
        for candidate in chunk.candidates or []:
            finish = candidate.finish_reason or finish
            for part in (candidate.content.parts or []) if candidate.content else []:
                parts.append(part)
                if part.text and not part.thought:
                    await publish(part.text)
    if finish!=types.FinishReason.STOP:
        raise ProviderError('invalid_response','Gemini devolvió una respuesta incompleta; no se ejecutaron herramientas parciales.')
    message = result_message(parts)
    return dict(message=message,usage=usage,finish_reason='tool_calls' if message.get('tool_calls') else 'stop')
