"""Reuse the OS vault; remote identities are scoped to the client and source kind."""
import json
from typing import Any
from ..agents.runtime_config import vault


def secret(client: Any, kind: str, value: dict[str,str] | None = None) -> dict[str,str]:
    service = 'FinOps Agent App · Source · '+client.profile.client_id
    if value is not None:
        allowed = {'s3':{'access_key','secret_key','session_token'},'gcs':{'service_account_json'},
            'bigquery':{'service_account_json'},'azure':{'sas_token'}}
        if not value.keys()<=allowed[kind]:
            raise ValueError('Campos de credencial no admitidos para este proveedor.')
        if len(json.dumps(value))>20000:
            raise ValueError('Credencial demasiado grande.')
    try:
        if value is not None:
            vault().set_password(service,kind,json.dumps(value))
        encoded = vault().get_password(service,kind)
    except Exception:
        if value is not None:
            raise ValueError('No se pudo guardar la credencial en el llavero.') from None
        raise ValueError('El llavero no está disponible; no se usará una identidad diferente silenciosamente.') from None
    return dict(json.loads(encoded)) if encoded else {}


def google_credentials(client: Any, kind: str) -> Any:
    values = secret(client,kind)
    if values.get('service_account_json'):
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_info(json.loads(values['service_account_json']),
            scopes=['https://www.googleapis.com/auth/cloud-platform'])
    return None
