"""Persist independent provider preferences without credentials in JSON."""
import json
from typing import Any,Literal
from pydantic import Field
from . import runtime_config

GEMINI_SERVICE = 'FinOps Agent App · Gemini'
GROQ_SERVICE = 'FinOps Agent App · Groq'
CREDENTIALS = {'gemini':('GOOGLE_API_KEY',GEMINI_SERVICE),'groq':('GROQ_API_KEY',GROQ_SERVICE)}
_session: dict[str,str] = {}


class SelectionUpdate(runtime_config.ProviderUpdate):
    provider: Literal['nvidia','gemini','groq'] = 'nvidia'
    project: str = Field(default='',pattern=r'^[a-z0-9.-]{0,150}$')
    location: str = Field(default='global',pattern=r'^[a-z0-9-]{1,50}$')


def saved() -> dict[str,Any]:
    path = runtime_config.PATH.with_name('provider.json')
    return dict(json.loads(path.read_text())) if path.exists() else {}


def selection_overrides(provider: str | None = None) -> dict[str,str]:
    document = saved()
    result = dict(document.get(provider or '',{})) if provider in CREDENTIALS else {}
    if provider in CREDENTIALS:
        key = CREDENTIALS[provider][0]
        if key in _session:
            result[key] = _session[key]
    if not provider and document.get('provider'):
        result['FINOPS_LLM_PROVIDER'] = document['provider']
    return result


def load_key() -> None:
    for key_name,service in CREDENTIALS.values():
        try:
            key = runtime_config.vault().get_password(service,runtime_config.ACCOUNT)
        except Exception:
            key = None
        if key:
            _session[key_name] = key


def select(body: SelectionUpdate) -> None:
    document = saved()
    if body.provider=='nvidia':
        runtime_config.update(runtime_config.ProviderUpdate(**body.model_dump(exclude={'provider','project','location'})))
    elif body.provider=='gemini':
        if not body.project:
            raise ValueError('Indica el proyecto de Google Cloud.')
        store_provider_key(body)
        document['gemini'] = dict(GEMINI_MODEL=body.model,GOOGLE_CLOUD_PROJECT=body.project,
            GOOGLE_CLOUD_LOCATION=body.location,FINOPS_LLM_READ_TIMEOUT=str(body.read_timeout_seconds))
    else:
        store_provider_key(body)
        document['groq'] = dict(GROQ_MODEL=body.model,FINOPS_LLM_READ_TIMEOUT=str(body.read_timeout_seconds))
    document['provider'] = body.provider
    runtime_config.atomic_write_text(runtime_config.PATH.with_name('provider.json'),json.dumps(document))


def store_provider_key(body: SelectionUpdate) -> None:
    key = body.api_key.get_secret_value().strip() if body.api_key else ''
    if not key:
        return
    if not 8<=len(key)<=512 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise ValueError('La API key no tiene un formato válido.')
    key_name,service = CREDENTIALS[body.provider]
    if body.persist_key:
        try:
            vault = runtime_config.vault()
            vault.set_password(service,runtime_config.ACCOUNT,key)
            if vault.get_password(service,runtime_config.ACCOUNT)!=key:
                raise RuntimeError('Keychain verification failed')
        except Exception:
            raise ValueError('No se pudo guardar en el llavero; revisa sus permisos o usa solo esta sesión.') from None
    _session[key_name] = key


def profiles() -> list[dict[str,Any]]:
    from .nvidia import settings
    from .groq_provider import DEFAULT_MODEL,MODEL_OPTIONS
    result = []
    for provider,label,key,model in [('nvidia','NVIDIA','NVIDIA_API_KEY','FINOPS_LLM_MODEL'),('gemini','Gemini','GOOGLE_API_KEY','GEMINI_MODEL'),('groq','Groq','GROQ_API_KEY','GROQ_MODEL')]:
        config = settings(provider)
        result.append(dict(id=provider,provider=label,configured=bool(config.get(key)),
            model=config.get(model,{'nvidia':'z-ai/glm-5.3-flash','gemini':'gemini-3.6-flash','groq':DEFAULT_MODEL}[provider]),
            fallback_model=config.get('FINOPS_LLM_FALLBACK_MODEL','') if provider=='nvidia' else '',
            project=config.get('GOOGLE_CLOUD_PROJECT','') if provider=='gemini' else '',
            model_options=MODEL_OPTIONS if provider=='groq' else [],
            location=config.get('GOOGLE_CLOUD_LOCATION','global'),
            read_timeout_seconds=int(float(config.get('FINOPS_LLM_READ_TIMEOUT','90')))))
    return result
