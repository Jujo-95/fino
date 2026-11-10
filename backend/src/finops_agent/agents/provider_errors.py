from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any
import httpx


class ProviderError(ValueError):
    def __init__(self, code: str, message: str, retryable: bool = False, retry_after: float = 0,
                 request_id: str | None = None) -> None:
        super().__init__(message)
        self.code,self.retryable,self.retry_after,self.request_id = code,retryable,retry_after,request_id

    def public(self) -> dict[str, Any]:
        return dict(code=self.code,message=str(self),retryable=self.retryable,
                    retry_after_seconds=self.retry_after,request_id=self.request_id)


def retry_delay(value: str | None) -> float:
    try:
        return max(0,float(value or '0'))
    except ValueError:
        try:
            return max(0,(parsedate_to_datetime(value or '')-datetime.now(timezone.utc)).total_seconds())
        except (ValueError,TypeError):
            return 0


def http_failure(response: httpx.Response) -> ProviderError:
    status = response.status_code
    code = {401:'invalid_credentials',403:'access_denied',404:'model_not_found',429:'provider_rate_limit'}.get(status,
           'provider_unavailable' if status>=500 else 'invalid_request')
    message = {401:'La API key NVIDIA fue rechazada.',403:'La clave no tiene acceso al modelo NVIDIA.',
               404:'NVIDIA no encuentra el modelo configurado.',429:'NVIDIA limitó las solicitudes; espera antes de reintentar.'}.get(status,
               'NVIDIA no está disponible temporalmente.' if status>=500 else 'NVIDIA rechazó la solicitud.')
    return ProviderError(code,f'NVIDIA HTTP {status}: {message}',status in (408,429,500,502,503,504),
                         retry_delay(response.headers.get('retry-after')),response.headers.get('x-request-id'))


def transport_failure(error: httpx.HTTPError, partial: bool = False) -> ProviderError:
    if partial:
        return ProviderError('stream_interrupted','La respuesta NVIDIA se interrumpió. Puedes reanudar desde el último paso confirmado.')
    code = 'read_timeout' if isinstance(error,httpx.ReadTimeout) else 'connect_timeout' if isinstance(error,httpx.ConnectTimeout) else 'connection_error'
    text = 'NVIDIA no respondió dentro del tiempo permitido.' if isinstance(error,httpx.TimeoutException) else 'No se pudo conectar con NVIDIA.'
    return ProviderError(code,text,True)
