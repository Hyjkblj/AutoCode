"""
Feature flag implementation for canary deployment support.

Provides Redis-backed feature flags with canary percentage-based rollout.
Traffic routing uses a consistent hash of the task_id so the same task
always routes to the same component throughout its lifetime.

**Validates: Requirements 11.3, 11.4, 11.6, 11.7**
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature flag definitions
# ---------------------------------------------------------------------------


class FeatureFlag(str, Enum):
    """
    Enumeration of all feature flags used in the Backend Upgrade 2.0 rollout.

    Each flag controls one upgrade component and can be independently enabled,
    disabled, or set to a canary percentage.
    """

    # LangGraph orchestration engine (replaces legacy orchestrator)
    LANGGRAPH_ENGINE = "langgraph_engine"

    # Enhanced Flask/FastAPI backend generator
    NEW_BACKEND_GENERATOR = "new_backend_generator"

    # Spring Cloud Gateway as unified entry point
    SPRING_CLOUD_GATEWAY = "spring_cloud_gateway"

    # Extracted Artifact Service microservice
    ARTIFACT_MICROSERVICE = "artifact_microservice"

    # Extracted Event Service microservice
    EVENT_MICROSERVICE = "event_microservice"

    # Extracted Approval Service microservice
    APPROVAL_MICROSERVICE = "approval_microservice"

    # Enhanced validation gate with runtime checks
    NEW_VALIDATION_GATE = "new_validation_gate"

    # Updated distributed lock implementation
    DISTRIBUTED_LOCK_V2 = "distributed_lock_v2"


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

_KEY_PREFIX = "feature_flag"


def _enabled_key(flag: FeatureFlag) -> str:
    return f"{_KEY_PREFIX}:{flag.value}:enabled"


def _canary_key(flag: FeatureFlag) -> str:
    return f"{_KEY_PREFIX}:{flag.value}:canary_percentage"


def _updated_at_key(flag: FeatureFlag) -> str:
    return f"{_KEY_PREFIX}:{flag.value}:updated_at"


def _updated_by_key(flag: FeatureFlag) -> str:
    return f"{_KEY_PREFIX}:{flag.value}:updated_by"


# ---------------------------------------------------------------------------
# Canary routing helper
# ---------------------------------------------------------------------------


def _canary_bucket(task_id: str) -> int:
    """
    Return a stable bucket in [0, 99] for the given task_id.

    Uses MD5 for speed (not security). The same task_id always maps to the
    same bucket, ensuring a task never switches components mid-execution.
    """
    digest = hashlib.md5(task_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


# ---------------------------------------------------------------------------
# FeatureFlagManager
# ---------------------------------------------------------------------------


class FeatureFlagManager:
    """
    Manages feature flags backed by Redis.

    Each flag has two independent controls:
    - ``enabled``: master switch; when False the flag is always off regardless
      of canary_percentage.
    - ``canary_percentage``: 0–100 integer controlling what fraction of
      task_ids are routed to the new component when the flag is enabled.
      100 means all traffic; 0 means no traffic (equivalent to disabled).

    If Redis is unavailable, all flags default to ``False`` (legacy path) so
    the system degrades gracefully.

    Usage::

        manager = FeatureFlagManager(redis_client)

        # Enable LangGraph for 5% of tasks
        manager.set_flag(FeatureFlag.LANGGRAPH_ENGINE, enabled=True, canary_percentage=5)

        # Check whether a specific task should use LangGraph
        if manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, task_id="task-abc-123"):
            run_langgraph()
        else:
            run_legacy()
    """

    def __init__(self, redis_client, redis_timeout_seconds: float = 0.1) -> None:
        """
        Parameters
        ----------
        redis_client:
            A Redis client instance (e.g. ``redis.Redis(...)``).
        redis_timeout_seconds:
            Maximum time to wait for a Redis operation before falling back to
            the legacy path. Defaults to 100 ms.
        """
        self._redis = redis_client
        self._timeout = redis_timeout_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_enabled(self, flag: FeatureFlag, task_id: str = "") -> bool:
        """
        Return True if the feature flag is active for the given task_id.

        Routing logic:
        1. If the flag's ``enabled`` key is not ``"true"``, return False.
        2. Read ``canary_percentage`` (default 0 if missing).
        3. Compute the task's canary bucket (0–99).
        4. Return True iff bucket < canary_percentage.

        When ``task_id`` is empty, bucket 0 is used (deterministic).

        Falls back to False on any Redis error.
        """
        try:
            raw_enabled = self._redis.get(_enabled_key(flag))
            if raw_enabled is None or raw_enabled.decode("utf-8").lower() != "true":
                return False

            raw_pct = self._redis.get(_canary_key(flag))
            if raw_pct is None:
                canary_pct = 0
            else:
                try:
                    canary_pct = int(raw_pct.decode("utf-8"))
                except ValueError:
                    canary_pct = 0

            # Clamp to valid range
            canary_pct = max(0, min(100, canary_pct))

            if canary_pct == 0:
                return False
            if canary_pct >= 100:
                return True

            bucket = _canary_bucket(task_id) if task_id else 0
            return bucket < canary_pct

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "FeatureFlagManager: Redis error reading flag %s — defaulting to False. "
                "Error: %s",
                flag.value,
                exc,
            )
            return False

    def set_flag(
        self,
        flag: FeatureFlag,
        enabled: bool,
        canary_percentage: int = 100,
        updated_by: str = "system",
    ) -> None:
        """
        Set a feature flag's enabled state and canary percentage.

        Parameters
        ----------
        flag:
            The feature flag to update.
        enabled:
            Master switch. Set to False to disable the flag entirely.
        canary_percentage:
            Percentage of task_ids to route to the new component (0–100).
            Only meaningful when ``enabled=True``.
        updated_by:
            Identifier of the operator making the change (for audit trail).

        Raises
        ------
        ValueError
            If ``canary_percentage`` is outside [0, 100].
        """
        if not 0 <= canary_percentage <= 100:
            raise ValueError(
                f"canary_percentage must be between 0 and 100, got {canary_percentage}"
            )

        now_iso = datetime.now(timezone.utc).isoformat()

        pipe = self._redis.pipeline()
        pipe.set(_enabled_key(flag), "true" if enabled else "false")
        pipe.set(_canary_key(flag), str(canary_percentage))
        pipe.set(_updated_at_key(flag), now_iso)
        pipe.set(_updated_by_key(flag), updated_by)
        pipe.execute()

        logger.info(
            "FeatureFlagManager: flag=%s enabled=%s canary_percentage=%d updated_by=%s",
            flag.value,
            enabled,
            canary_percentage,
            updated_by,
        )

    def get_flag_state(self, flag: FeatureFlag) -> dict:
        """
        Return the full state of a feature flag as a dictionary.

        Returns
        -------
        dict with keys: flag, enabled, canary_percentage, updated_at, updated_by
        """
        try:
            raw_enabled = self._redis.get(_enabled_key(flag))
            raw_pct = self._redis.get(_canary_key(flag))
            raw_updated_at = self._redis.get(_updated_at_key(flag))
            raw_updated_by = self._redis.get(_updated_by_key(flag))

            enabled = (
                raw_enabled is not None
                and raw_enabled.decode("utf-8").lower() == "true"
            )
            try:
                canary_pct = int(raw_pct.decode("utf-8")) if raw_pct else 0
            except ValueError:
                canary_pct = 0

            return {
                "flag": flag.value,
                "enabled": enabled,
                "canary_percentage": canary_pct,
                "updated_at": raw_updated_at.decode("utf-8") if raw_updated_at else None,
                "updated_by": raw_updated_by.decode("utf-8") if raw_updated_by else None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "FeatureFlagManager: Redis error reading state for flag %s. Error: %s",
                flag.value,
                exc,
            )
            return {
                "flag": flag.value,
                "enabled": False,
                "canary_percentage": 0,
                "updated_at": None,
                "updated_by": None,
            }

    def disable_flag(self, flag: FeatureFlag, updated_by: str = "system") -> None:
        """
        Immediately disable a feature flag (rollback to legacy path).

        This is the primary rollback mechanism: sets enabled=False and
        canary_percentage=0 atomically.
        """
        self.set_flag(flag, enabled=False, canary_percentage=0, updated_by=updated_by)
        logger.warning(
            "FeatureFlagManager: flag=%s DISABLED (rollback) by %s",
            flag.value,
            updated_by,
        )

    def list_flags(self) -> list[dict]:
        """Return the state of all known feature flags."""
        return [self.get_flag_state(flag) for flag in FeatureFlag]
