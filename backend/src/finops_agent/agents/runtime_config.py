"""Runtime provider preferences; secrets live only in memory and macOS Keychain."""
import json
import platform
import os
import re
import threading
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from ..config import ROOT, atomic_write_text

PATH = ROOT/'.runtime/nvidia.json'
SERVICE, ACCOUNT = 'FinOps Agent App · NVIDIA', 'api-key'
_lock = threading.RLock()
_values: dict[str,str] = {}
_source = 'environment'


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    api_key: SecretStr | None = None
    persist_key: bool = True
    model: str = Field(pattern=r'^[a-zA-Z0-9/._-]{1,150}$')
    fallback_model: str = Field(default='',pattern=r'^[a-zA-Z0-9/._-]{0,150}$')
    read_timeout_seconds: int = Field(default=90,ge=15,le=180)


def vault() -> Any:
    if platform.system()!='Darwin':
        raise RuntimeError('El llavero seguro del sistema no está disponible.')
    from keyring.backends.macOS import Keyring
    return Keyring()


def load() -> None:
    global _source
    if os.getenv('FINOPS_LLM_PROVIDER')=='mock':
        return
    with _lock:
        if PATH.exists():
            saved = json.loads(PATH.read_text())
            _values.update({k:str(v) for k,v in saved.items() if k in ('FINOPS_LLM_MODEL','FINOPS_LLM_FALLBACK_MODEL','FINOPS_LLM_READ_TIMEOUT')})
        try:
            key = vault().get_password(SERVICE,ACCOUNT)
        except Exception:
            key = None
        if key:
            _values['NVIDIA_API_KEY'],_source = key,'keychain'
        from .provider_selection import load_key
        load_key()


def overrides() -> dict[str,str]:
    with _lock:
        return dict(_values)


def public() -> dict[str,Any]:
    return dict(credential_source=_source,secure_storage=platform.system()=='Darwin')


def update(body: ProviderUpdate) -> None:
    global _source
    key = body.api_key.get_secret_value().strip() if body.api_key else ''
    if key and (not 8<=len(key)<=512 or any(ord(c)<33 or ord(c)>126 for c in key)):
        raise ValueError('La clave NVIDIA no tiene un formato válido.')
    safe = dict(FINOPS_LLM_MODEL=body.model,FINOPS_LLM_FALLBACK_MODEL=body.fallback_model,
                FINOPS_LLM_READ_TIMEOUT=str(body.read_timeout_seconds))
    with _lock:
        if key and body.persist_key:
            try:
                secure = vault()
                secure.set_password(SERVICE,ACCOUNT,key)
                if secure.get_password(SERVICE,ACCOUNT)!=key:
                    raise RuntimeError('No se pudo verificar el llavero.')
            except Exception:
                raise ValueError('No se pudo guardar en el llavero de macOS. Revisa su permiso o usa solo esta sesión.') from None
        if key and body.persist_key:
            remove_legacy_key()
        atomic_write_text(PATH,json.dumps(safe))
        _values.update(safe)
        if key:
            _values['NVIDIA_API_KEY'],_source = key,'keychain' if body.persist_key else 'memory'


def remove_legacy_key() -> None:
    path = ROOT/'.env'
    if path.exists():
        cleaned = re.sub(r'(?m)^(?:export\s+)?NVIDIA_API_KEY\s*=.*(?:\n|$)','',path.read_text())
        atomic_write_text(path,cleaned)
