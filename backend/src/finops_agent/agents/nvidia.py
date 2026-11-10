import os
from datetime import datetime, timezone
from typing import Any
import httpx
from dotenv import dotenv_values
from ..config import ROOT
from .provider_errors import ProviderError, http_failure, transport_failure
from .provider_policy import ProviderPolicy
from .provider_fallback import CompletionTransport


def settings(provider: str | None = None) -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
    from .runtime_config import overrides
    from .provider_selection import selection_overrides
    combined = {**values, **os.environ}
    if combined.get('FINOPS_LLM_PROVIDER')!='mock' and provider is None:
        combined.update(selection_overrides())
    selected = provider or combined.get('FINOPS_LLM_PROVIDER','nvidia')
    runtime = overrides()
    if selected not in ('nvidia','mock'):
        runtime = {k:v for k,v in runtime.items() if k=='NVIDIA_API_KEY'}
    return {**combined, **runtime, **selection_overrides(selected)}



class NvidiaProvider:
    """OpenAI-compatible native tool calling. No simulated fallback on API failure."""
    native_tools = True

    def __init__(self) -> None:
        self.policy = ProviderPolicy(settings())
        self.transport = CompletionTransport(self.policy,settings().get('FINOPS_LLM_FALLBACK_MODEL',''))
        self.verified_at: str | None = None
        self.model = settings().get("FINOPS_LLM_MODEL", "z-ai/glm-5.3-flash")

    def readiness(self) -> dict[str, Any]:
        return dict(provider="NVIDIA", model=self.model, configured=bool(settings().get("NVIDIA_API_KEY")),
                    mode="llm_agent", verified_at_utc=self.verified_at, base_url="https://integrate.api.nvidia.com/v1",limits=self.policy.public(),fallback_model=self.transport.fallback_model or None)

    def audit_config(self) -> dict[str, Any]:
        config = settings()
        return dict(model=self.model, temperature=0.5, top_p=1, stream=False,
                    max_tokens=int(config.get("FINOPS_MAX_TOKENS", "4096")),
                    reasoning_effort=config.get("FINOPS_REASONING_EFFORT", "low"),fallback_model=self.transport.fallback_model or None)

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        config = settings()
        key = config.get("NVIDIA_API_KEY")
        if not key:
            raise ValueError("NVIDIA_API_KEY no configurada en .env; no se ejecutará un sustituto por reglas.")
        body = self.payload(messages,tools)
        self.policy.bind_key(key)
        response = await self.transport.request(key,body)
        if response.is_error:
            raise ValueError(f"NVIDIA HTTP {response.status_code}; revisar modelo, permisos y cuota.")
        try:
            data = response.json()
            choice = data["choices"][0]
            if not isinstance(choice.get('message'),dict):
                raise ValueError('Missing message')
        except (ValueError,KeyError,IndexError,TypeError):
            raise ProviderError('invalid_response','NVIDIA devolvió una respuesta no válida.') from None
        if choice.get("finish_reason") == "length":
            raise ValueError("NVIDIA agotó max_tokens; aumente FINOPS_MAX_TOKENS y reintente.")
        self.verified_at = datetime.now(timezone.utc).isoformat()
        message = choice["message"]
        # Retain observable actions and final explanations; never persist private reasoning_content.
        safe = {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
        return dict(message=safe,usage=data.get("usage",{}),finish_reason=choice.get("finish_reason"),**{key:response.extensions.get(key) for key in ("model","requested_model","fallback","fallback_reason")})


    async def complete_for_report(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], max_tokens: int | None = None) -> dict[str, Any]:
        async def discard(_text: str) -> None:
            pass
        setattr(discard,'retry_partial',True)
        return await self.stream_complete(messages,tools,discard,max_tokens)

    def payload(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], stream: bool = False) -> dict[str, Any]:
        config = settings()
        body = dict(model=self.model, messages=[{k:v for k,v in m.items() if k!='provider_content'} for m in messages], tools=tools, tool_choice="auto",
                    temperature=0.5, top_p=1, reasoning_effort=config.get("FINOPS_REASONING_EFFORT", "low"),
                    max_tokens=int(config.get("FINOPS_MAX_TOKENS", "4096")), stream=stream)
        if messages and messages[-1].get("role") == "user" and str(messages[-1].get("content", "")).startswith("Use the tools, then submit_analysis"):
            body["tool_choice"] = {"type": "function", "function": {"name": "submit_analysis"}}
        return body

    async def stream_complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], on_text: Any, max_tokens: int | None = None) -> dict[str, Any]:
        key = settings().get('NVIDIA_API_KEY')
        if not key:
            raise ValueError('NVIDIA_API_KEY no configurada; no se usa un sustituto.')
        self.policy.bind_key(key)
        body = self.payload(messages,tools,stream=True)
        if max_tokens is not None:
            body['max_tokens'] = max_tokens
        result = await self.transport.request(key,body,on_text)
        self.verified_at = datetime.now(timezone.utc).isoformat()
        return result


async def post_completion(key: str, body: dict[str, Any], read_timeout: float = 60) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(read_timeout,connect=10,write=20,pool=10)) as client:
            response = await client.post("https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization":"Bearer "+key},json=body)
        if response.is_error:
            raise http_failure(response)
        return response
    except httpx.HTTPError as error:
        raise transport_failure(error) from None
