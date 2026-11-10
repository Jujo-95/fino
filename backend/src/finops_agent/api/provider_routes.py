from typing import Any
from urllib.parse import urlsplit
from fastapi import Request
from pydantic import ValidationError
from .routes import router, Container
from ..agents.provider_selection import SelectionUpdate,profiles
from .provider_switch import switch_provider


def local_write(request: Request) -> None:
    host = urlsplit(str(request.url)).hostname
    origin = request.headers.get('origin')
    if host not in ('127.0.0.1','localhost','::1') or request.headers.get('sec-fetch-site')=='cross-site':
        raise ValueError('La configuración solo puede cambiarse desde la app local.')
    if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
        raise ValueError('Origen no autorizado para cambiar la conexión.')
    if request.headers.get('x-finops-config')!='1':
        raise ValueError('Falta el encabezado de configuración de la app.')


@router.put('/runtime/provider')
async def configure_provider(request: Request, c: Container) -> dict[str,Any]:
    local_write(request)
    c.request_limits.admit('runtime-config',10,0,1)
    try:
        body = SelectionUpdate.model_validate(await request.json())
    except (ValidationError,ValueError,TypeError):
        raise ValueError('Revisa los campos de conexión; no se ha guardado la configuración.') from None
    return switch_provider(c,body)


@router.get('/runtime/providers')
def provider_options(c: Container) -> dict[str,Any]:
    active = c.llm.readiness()['provider'].lower() if hasattr(c.llm,'readiness') else None
    return dict(active=active,providers=profiles())
