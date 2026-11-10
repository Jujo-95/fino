import math
import threading
from collections import deque
from time import monotonic


class AdmissionError(ValueError):
    def __init__(self, message: str, retry_after: int = 5) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RequestLimits:
    """Single local backend process; limits logical work, not reconnects/SSE reads."""
    def __init__(self) -> None:
        self.windows: dict[str, deque[float]] = {}
        self.lock = threading.Lock()

    def admit(self, key: str, limit: int, active: int, maximum: int) -> None:
        with self.lock:
            if active>=maximum:
                raise AdmissionError('Hay demasiados trabajos activos. Espera a que termine uno.')
            now = monotonic()
            window = self.windows.setdefault(key,deque())
            while window and window[0]<=now-60:
                window.popleft()
            if len(window)>=limit:
                raise AdmissionError('Has alcanzado el límite de solicitudes por minuto.',max(1,math.ceil(60-now+window[0])))
            window.append(now)
