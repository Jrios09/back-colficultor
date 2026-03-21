from collections import defaultdict, deque
from threading import Lock
from time import time


class InMemoryRateLimiter:
    """Rate limiter básico para preparar protección de abuso.

    Nota: en despliegues con múltiples instancias debe reemplazarse por
    un backend distribuido (Redis u otro) para consistencia global.
    """

    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time()
        window_start = now - window_seconds

        with self._lock:
            bucket = self._attempts[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= limit:
                return False

            bucket.append(now)
            return True
