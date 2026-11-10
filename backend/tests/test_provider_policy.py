import asyncio
from unittest.mock import patch
import httpx
import pytest
from finops_agent.agents.provider_policy import ProviderPolicy
from finops_agent.agents.provider_errors import ProviderError, http_failure, transport_failure
from finops_agent.agents.nvidia import NvidiaProvider
from finops_agent.api.admission import RequestLimits, AdmissionError


class FastLimiter:
    async def aacquire(self):
        return True


def policy(attempts=2):
    value = ProviderPolicy({"FINOPS_LLM_ATTEMPTS": str(attempts), "FINOPS_LLM_CONCURRENCY": "1"})
    value.limiter = FastLimiter()
    return value


@pytest.mark.asyncio
async def test_transient_retry_and_rate_tokens_each_attempt():
    p = policy()
    calls = []

    async def call():
        calls.append(1)
        if len(calls) == 1:
            raise transport_failure(httpx.ReadTimeout("private-request"))
        return "ok"

    with patch("finops_agent.agents.provider_policy.wait_random_exponential", return_value=lambda state: 0):
        assert await p.run(call) == "ok"
    assert len(calls) == 2 and p.pending == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "invalid_credentials"),
        (403, "access_denied"),
        (429, "provider_rate_limit"),
        (503, "provider_unavailable"),
    ],
)
async def test_http_classification_and_retry_after(status, code):
    error = http_failure(httpx.Response(status, headers={"Retry-After": "45", "x-request-id": "support-ref"}))
    assert error.code == code and error.retry_after == 45
    calls = []

    async def call():
        calls.append(1)
        raise error

    with pytest.raises(ProviderError):
        await policy().run(call)
    assert len(calls) == 1
    assert error.public()["request_id"] == "support-ref"


@pytest.mark.asyncio
async def test_partial_stream_never_replayed_and_circuit_recovers_on_key_rotation():
    p = policy()
    p.bind_key("first")
    calls = []

    async def fail():
        calls.append(1)
        raise transport_failure(httpx.ReadTimeout("private"), partial=True)

    for _ in range(3):
        with pytest.raises(ProviderError, match="interrumpió"):
            await p.run(fail)
    with pytest.raises(ProviderError, match="pausa"):
        await p.run(fail)
    assert len(calls) == 3
    p.bind_key("new")
    assert not p.public()["circuit_open"]
    assert "first" not in str(p.public())


@pytest.mark.asyncio
async def test_bounded_concurrency_and_queue_rejection():
    p = policy()
    p.max_pending = 1
    entered = asyncio.Event()
    release = asyncio.Event()

    async def call():
        entered.set()
        await release.wait()
        return "ok"

    job = asyncio.create_task(p.run(call))
    await entered.wait()
    with pytest.raises(ProviderError, match="espera"):
        await p.run(call)
    release.set()
    assert await job == "ok"
    assert p.pending == 0 and p.slots._value == 1


def test_api_admission_has_retry_after_and_isolated_clients():
    limits = RequestLimits()
    limits.admit("chat:a", 1, 0, 4)
    with pytest.raises(AdmissionError) as raised:
        limits.admit("chat:a", 1, 0, 4)
    assert 1 <= raised.value.retry_after <= 60
    limits.admit("chat:b", 1, 0, 4)
    with pytest.raises(AdmissionError):
        limits.admit("chat:b", 5, 4, 4)


@pytest.mark.asyncio
async def test_new_key_is_read_per_call_without_restart():
    keys = []

    async def post(self, url, **kwargs):
        keys.append(kwargs["headers"]["Authorization"])
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}]},
        )

    with patch("finops_agent.agents.nvidia.settings", return_value={"NVIDIA_API_KEY": "first"}):
        provider = NvidiaProvider()
        provider.policy = policy()
        provider.transport.policy = provider.policy
        with patch.object(httpx.AsyncClient, "post", post):
            await provider.complete([], [])
            with patch("finops_agent.agents.nvidia.settings", return_value={"NVIDIA_API_KEY": "second"}):
                await provider.complete([], [])
    assert keys == ["Bearer first", "Bearer second"]


@pytest.mark.asyncio
async def test_standard_fallback_records_model_and_does_not_replay_auth_or_stream():
    from finops_agent.agents.provider_fallback import CompletionTransport

    p = policy()
    transport = CompletionTransport(p, "backup")
    calls = []

    async def call(key, body, on_text, attempts=None):
        calls.append(body["model"])
        if body["model"] == "primary":
            raise ProviderError("read_timeout", "timeout", True)
        return {"model": "backup", "message": {"content": "ok"}}

    transport.call = call
    result = await transport.request("not-printed", {"model": "primary"})
    assert result["model"] == "backup" and result["fallback"]
    assert result["fallback_reason"] == "read_timeout"
    await transport.request("not-printed", {"model": "primary"})
    assert calls == ["primary", "backup", "backup"]
    transport.prefer_backup_until = 0

    async def denied(key, body, on_text, attempts=None):
        calls.append(body["model"])
        raise ProviderError("invalid_credentials", "denied")

    transport.call = denied
    with pytest.raises(ProviderError):
        await transport.request("not-printed", {"model": "primary"})
    assert calls[-1] == "primary"
