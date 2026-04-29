from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import Callable
from typing import TypeVar


T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
    ) -> None:
        self.name = name.strip() or "default"
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout_seconds = max(1.0, float(recovery_timeout_seconds))
        self._lock = Lock()
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = 0.0

    def call(self, operation: Callable[[], T]) -> T:
        self._before_call()
        try:
            result = operation()
        except Exception:
            self._after_failure()
            raise
        self._after_success()
        return result

    def _before_call(self) -> None:
        with self._lock:
            if self._state != "open":
                return
            elapsed = monotonic() - self._opened_at
            if elapsed >= self.recovery_timeout_seconds:
                self._state = "half_open"
                return
            raise CircuitBreakerOpenError(f"circuit breaker open: {self.name}")

    def _after_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._opened_at = 0.0

    def _after_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == "half_open" or self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._opened_at = monotonic()

    def state(self) -> dict[str, object]:
        with self._lock:
            return {
                "name": self.name,
                "status": self._state,
                "failureCount": self._failure_count,
                "openedAt": self._opened_at or None,
            }
