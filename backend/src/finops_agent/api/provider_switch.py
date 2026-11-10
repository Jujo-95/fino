"""Apply provider selection only between jobs, preserving provider limiters."""
from typing import Any
from fastapi import HTTPException
from ..agents import runtime_config
from ..agents.provider_selection import SelectionUpdate,select
from ..agents.nvidia import NvidiaProvider,settings
from ..agents.gemini import GeminiProvider
from ..agents.groq_provider import GroqProvider


def switch_provider(c: Any, body: SelectionUpdate) -> dict[str,Any]:
    if any(not task.done() for jobs in (c.jobs,c.chat) for task in jobs.tasks.values()):
        raise HTTPException(status_code=409,detail='Hay un análisis en curso. Espera a que termine o detenlo antes de cambiar el proveedor.')
    with c.resource_lock:
        select(body)
        instances = getattr(c,'provider_instances',{})
        if c.llm is not None and hasattr(c.llm,'readiness'):
            instances[c.llm.readiness()['provider'].lower()] = c.llm
        provider: Any = instances.get(body.provider)
        if provider is None:
            provider = {'nvidia':NvidiaProvider,'gemini':GeminiProvider,'groq':GroqProvider}[body.provider]()
        configure_instance(provider,body)
        instances[body.provider] = provider
        c.provider_instances,c.llm = instances,provider
    return {'status':'saved',**runtime_config.public(),**provider.readiness()}


def configure_instance(provider: Any, body: SelectionUpdate) -> None:
    config = settings(body.provider)
    provider.model = body.model
    provider.policy.read_timeout = body.read_timeout_seconds
    provider.verified_at = None
    if body.provider=='nvidia':
        provider.transport.fallback_model = body.fallback_model
        provider.transport.prefer_backup_until = 0
        provider.policy.bind_key(config.get('NVIDIA_API_KEY',''))
    elif body.provider=='gemini':
        provider.project,provider.location = body.project,body.location
        provider.policy.bind_key(config.get('GOOGLE_API_KEY',''))

    else:
        provider.policy.bind_key(config.get('GROQ_API_KEY',''))
