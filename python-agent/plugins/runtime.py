from __future__ import annotations

import os
from threading import Lock
from typing import Callable
from typing import TypeVar

from utils.circuit_breaker import CircuitBreaker


T = TypeVar("T")


class PluginRuntimeManager:
    def __init__(
        self,
        *,
        failure_threshold: int | None = None,
        recovery_timeout_seconds: float | None = None,
    ) -> None:
        self.failure_threshold = _resolve_failure_threshold(failure_threshold)
        self.recovery_timeout_seconds = _resolve_recovery_timeout(recovery_timeout_seconds)
        self._lock = Lock()
        self._breakers: dict[str, CircuitBreaker] = {}

    def execute(self, plugin_id: str, operation: Callable[[], T]) -> T:
        breaker = self._get_breaker(plugin_id)
        return breaker.call(operation)

    def state(self, plugin_id: str) -> dict[str, object]:
        breaker = self._get_breaker(plugin_id)
        state = breaker.state()
        state["pluginId"] = plugin_id
        state["failureThreshold"] = self.failure_threshold
        state["recoveryTimeoutSeconds"] = self.recovery_timeout_seconds
        return state

    def _get_breaker(self, plugin_id: str) -> CircuitBreaker:
        safe_plugin_id = str(plugin_id).strip() or "unknown-plugin"
        with self._lock:
            breaker = self._breakers.get(safe_plugin_id)
            if breaker is None:
                breaker = CircuitBreaker(
                    name=f"plugin:{safe_plugin_id}",
                    failure_threshold=self.failure_threshold,
                    recovery_timeout_seconds=self.recovery_timeout_seconds,
                )
                self._breakers[safe_plugin_id] = breaker
            return breaker


def _resolve_failure_threshold(value: int | None) -> int:
    if value is not None:
        return max(1, int(value))
    raw = os.getenv("MVP_PLUGIN_BREAKER_FAILURE_THRESHOLD", "").strip()
    if not raw:
        return 3
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def _resolve_recovery_timeout(value: float | None) -> float:
    if value is not None:
        return max(1.0, float(value))
    raw = os.getenv("MVP_PLUGIN_BREAKER_RECOVERY_SECONDS", "").strip()
    if not raw:
        return 30.0
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 30.0
