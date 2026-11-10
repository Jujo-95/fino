import asyncio
import hashlib
from time import monotonic
from typing import Any
from langchain_core.rate_limiters import InMemoryRateLimiter
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential
from .provider_errors import ProviderError


class ProviderPolicy:
    """Process-wide for the shared provider: token bucket, bounded queue, retry and circuit breaker."""
    def __init__(self, config: dict[str, str], provider: str = "NVIDIA") -> None:
        self.provider = provider
        self.rpm = max(1,int(config.get('FINOPS_LLM_RPM','30')))
        self.concurrency = max(1,int(config.get('FINOPS_LLM_CONCURRENCY','2')))
        self.attempts = min(3,max(1,int(config.get('FINOPS_LLM_ATTEMPTS','2'))))
        self.read_timeout = max(5,float(config.get('FINOPS_LLM_READ_TIMEOUT','60')))
        self.queue_timeout = max(1,float(config.get('FINOPS_LLM_QUEUE_TIMEOUT','30')))
        self.max_pending = max(self.concurrency,int(config.get('FINOPS_LLM_MAX_PENDING','8')))
        self.limiter = InMemoryRateLimiter(requests_per_second=self.rpm/60,check_every_n_seconds=.05,max_bucket_size=1)
        self.slots = asyncio.Semaphore(self.concurrency)
        self.pending,self.failures,self.open_until = 0,0,0.0
        self.key_hash = ''
        self.blocked_until = 0.0

    def bind_key(self, key: str) -> None:
        digest = hashlib.sha256(key.encode()).hexdigest()
        if digest!=self.key_hash:
            self.key_hash,self.failures,self.open_until,self.blocked_until = digest,0,0.0,0.0

    def check(self) -> None:
        if self.blocked_until>monotonic():
            raise ProviderError('provider_rate_limit',f'{self.provider} pidió reducir las solicitudes.',retry_after=round(self.blocked_until-monotonic(),1))
        if self.open_until>monotonic():
            raise ProviderError('circuit_open',f'{self.provider} está temporalmente en pausa tras fallos consecutivos.',
                                retry_after=round(self.open_until-monotonic(),1))

    async def attempt(self, call: Any) -> Any:
        self.check()
        try:
            async with asyncio.timeout(self.queue_timeout):
                await self.slots.acquire()
                try:
                    await self.limiter.aacquire()
                except BaseException:
                    self.slots.release()
                    raise
        except TimeoutError:
            raise ProviderError('local_rate_limit','La cola de solicitudes está ocupada. Intenta de nuevo en unos segundos.',retry_after=5) from None
        try:
            self.check()
            return await call()
        except ProviderError as error:
            if error.code=='provider_rate_limit':
                self.blocked_until = max(self.blocked_until,monotonic()+max(5,error.retry_after))
            raise
        finally:
            self.slots.release()

    async def run(self, call: Any, attempts: int | None = None) -> Any:
        self.check()
        if self.pending>=self.max_pending:
            raise ProviderError('local_rate_limit','Hay demasiadas solicitudes en espera.',retry_after=5)
        self.pending += 1
        wait = wait_random_exponential(multiplier=1,max=8)
        def delay(state: Any) -> float:
            error = state.outcome.exception()
            return max(wait(state),getattr(error,'retry_after',0))
        try:
            async for attempt in AsyncRetrying(stop=stop_after_attempt(attempts or self.attempts),
                    retry=retry_if_exception(lambda e:isinstance(e,ProviderError) and e.retryable and e.retry_after<=30),
                    wait=delay,reraise=True):
                with attempt:
                    result = await self.attempt(call)
            self.failures = 0
            return result
        except ProviderError as error:
            if error.retryable or error.code=='stream_interrupted':
                self.failures += 1
                if self.failures>=3:
                    self.open_until = monotonic()+30
            raise
        finally:
            self.pending -= 1

    def public(self) -> dict[str, Any]:
        return dict(requests_per_minute=self.rpm,max_concurrency=self.concurrency,max_attempts=self.attempts,
                    pending=self.pending,circuit_open=self.open_until>monotonic(),read_timeout_seconds=self.read_timeout)
