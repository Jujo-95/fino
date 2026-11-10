from time import monotonic
from typing import Any
from langchain_core.runnables import RunnableLambda
from .provider_errors import ProviderError


class FallbackSignal(Exception):
    pass


class CompletionTransport:
    def __init__(self, policy: Any, fallback_model: str = '') -> None:
        self.policy,self.fallback_model = policy,fallback_model
        self.prefer_backup_until = 0.0
        self.reason = ''

    async def request(self, key: str, body: dict[str, Any], on_text: Any = None) -> Any:
        primary_model = body['model']
        enabled = bool(self.fallback_model and self.fallback_model!=primary_model)
        async def primary(_: Any) -> Any:
            try:
                return await self.call(key,body,on_text,1 if enabled else None)
            except ProviderError as error:
                if enabled and error.code in ('read_timeout','connect_timeout','connection_error','provider_unavailable'):
                    self.reason = error.code
                    raise FallbackSignal(str(error)) from None
                raise
        async def backup(_: Any) -> Any:
            alternate = {**body,'model':self.fallback_model}
            alternate.pop('reasoning_effort',None)
            result = await self.call(key,alternate,on_text)
            self.prefer_backup_until = monotonic()+300
            return result
        if enabled and self.prefer_backup_until>monotonic():
            result = await backup(None)
        else:
            chain = RunnableLambda(primary).with_fallbacks([RunnableLambda(backup)],exceptions_to_handle=(FallbackSignal,))
            result = await chain.ainvoke(None)
        metadata = result if isinstance(result,dict) else result.extensions
        used = metadata.get('model',primary_model)
        metadata.update(requested_model=primary_model,fallback=used!=primary_model,
                        fallback_reason=self.reason if used!=primary_model else None)
        return result

    async def call(self, key: str, body: dict[str, Any], on_text: Any, attempts: int | None = None) -> Any:
        from .nvidia import post_completion
        from .nvidia_stream import stream_once
        async def invoke() -> Any:
            if on_text is not None:
                return await stream_once(key,body,on_text,self.policy.read_timeout)
            return await post_completion(key,body,self.policy.read_timeout)
        result = await self.policy.run(invoke,attempts)
        metadata = result if isinstance(result,dict) else result.extensions
        metadata['model'] = body['model']
        return result
