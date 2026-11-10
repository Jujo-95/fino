"""Cooperative cancellation crosses the worker thread into remote SDK queries."""
from contextvars import ContextVar
import threading
from typing import Any

stop_event: ContextVar[threading.Event | None] = ContextVar('analysis_stop',default=None)


class SourceError(ValueError):
    def __init__(self, error: Exception) -> None:
        name = getattr(error,'category',type(error).__name__)
        self.category = name
        self.transient = name in ('ServiceUnavailable','TooManyRequests','GatewayTimeout','ReadTimeout','ConnectTimeout','TimeoutError')
        super().__init__('La fuente no pudo completar la consulta ('+name+'). Revisa acceso, esquema, período y límites.')


def execute(remote: Any, client_id: str, sql: str, params: dict[str,Any]) -> list[dict[str,Any]]:
    from .remote_query import execute_remote
    stopped,finished = stop_event.get(),threading.Event()
    def watch() -> None:
        while not finished.wait(.1):
            if stopped and stopped.is_set():
                if hasattr(remote,'conn'):
                    remote.conn.interrupt()
                elif getattr(remote,'job',None):
                    remote.job.cancel()
                return
    monitor = threading.Thread(target=watch,daemon=True)
    if stopped:
        if stopped.is_set():
            raise InterruptedError('Consulta cancelada.')
        monitor.start()
    try:
        return execute_remote(remote,client_id,sql,params)
    finally:
        finished.set()
        if stopped:
            monitor.join(timeout=1)
