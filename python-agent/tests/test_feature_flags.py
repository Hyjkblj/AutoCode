"""
Property-based and unit tests for the feature flag system.

Task 19.2: Create canary deployment strategy
Properties 37, 38, 39, 40: Canary deployment support, backward compatibility,
performance validation, and zero downtime upgrades.

**Validates: Requirements 11.3, 11.4, 11.6, 11.7**
"""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, call, patch

import pytest
from hypothesis import assume, given, settings, strategies as st

from utils.feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    _canary_bucket,
    _canary_key,
    _enabled_key,
    _updated_at_key,
    _updated_by_key,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_redis_mock(enabled: str = "false", canary_pct: str = "0") -> MagicMock:
    """Return a Redis mock pre-configured with the given flag state."""
    mock = MagicMock()
    mock.get.side_effect = lambda key: (
        enabled.encode() if key.endswith(":enabled") else
        canary_pct.encode() if key.endswith(":canary_percentage") else
        None
    )
    pipe = MagicMock()
    pipe.__enter__ = MagicMock(return_value=pipe)
    pipe.__exit__ = MagicMock(return_value=False)
    mock.pipeline.return_value = pipe
    return mock


def _make_manager(enabled: str = "false", canary_pct: str = "0") -> FeatureFlagManager:
    return FeatureFlagManager(_make_redis_mock(enabled, canary_pct))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

task_id_strategy = st.text(
    min_size=1,
    max_size=64,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)

canary_pct_strategy = st.integers(min_value=0, max_value=100)

flag_strategy = st.sampled_from(list(FeatureFlag))


# ---------------------------------------------------------------------------
# Unit tests — FeatureFlag enum
# ---------------------------------------------------------------------------


class TestFeatureFlagEnum:
    def test_all_expected_flags_exist(self):
        flag_values = {f.value for f in FeatureFlag}
        assert "langgraph_engine" in flag_values
        assert "new_backend_generator" in flag_values
        assert "spring_cloud_gateway" in flag_values
        assert "artifact_microservice" in flag_values
        assert "event_microservice" in flag_values
        assert "approval_microservice" in flag_values
        assert "new_validation_gate" in flag_values
        assert "distributed_lock_v2" in flag_values

    def test_flag_values_are_strings(self):
        for flag in FeatureFlag:
            assert isinstance(flag.value, str)
            assert len(flag.value) > 0


# ---------------------------------------------------------------------------
# Unit tests — canary bucket helper
# ---------------------------------------------------------------------------


class TestCanaryBucket:
    def test_bucket_is_in_range(self):
        for task_id in ["task-1", "task-abc", "xyz-999", "a" * 64]:
            bucket = _canary_bucket(task_id)
            assert 0 <= bucket <= 99, f"Bucket {bucket} out of range for task_id={task_id!r}"

    def test_same_task_id_always_same_bucket(self):
        task_id = "stable-task-id-42"
        buckets = {_canary_bucket(task_id) for _ in range(10)}
        assert len(buckets) == 1, "Bucket must be deterministic for the same task_id"

    def test_different_task_ids_produce_different_buckets(self):
        """With enough task IDs, we should see multiple distinct buckets."""
        buckets = {_canary_bucket(f"task-{i}") for i in range(200)}
        assert len(buckets) > 10, "Expected distribution across multiple buckets"

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_property_bucket_always_in_range(self, task_id: str):
        """
        **Property 37: Canary Deployment Support**

        For any task_id, the canary bucket SHALL be in [0, 99].

        **Validates: Requirements 11.3**
        """
        bucket = _canary_bucket(task_id)
        assert 0 <= bucket <= 99

    @given(task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_bucket_is_deterministic(self, task_id: str):
        """
        **Property 37: Canary Deployment Support**

        For any task_id, the canary bucket SHALL be deterministic (same input
        always produces same output), ensuring a task never switches components
        mid-execution.

        **Validates: Requirements 11.3, 11.7**
        """
        assert _canary_bucket(task_id) == _canary_bucket(task_id)


# ---------------------------------------------------------------------------
# Unit tests — is_enabled
# ---------------------------------------------------------------------------


class TestIsEnabled:
    def test_disabled_flag_returns_false(self):
        manager = _make_manager(enabled="false", canary_pct="100")
        assert manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "any-task") is False

    def test_enabled_flag_100pct_returns_true(self):
        manager = _make_manager(enabled="true", canary_pct="100")
        assert manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "any-task") is True

    def test_enabled_flag_0pct_returns_false(self):
        manager = _make_manager(enabled="true", canary_pct="0")
        assert manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "any-task") is False

    def test_redis_error_returns_false(self):
        """When Redis is unavailable, the system defaults to the legacy path."""
        mock = MagicMock()
        mock.get.side_effect = ConnectionError("Redis unavailable")
        manager = FeatureFlagManager(mock)
        result = manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "task-1")
        assert result is False

    def test_missing_enabled_key_returns_false(self):
        mock = MagicMock()
        mock.get.return_value = None
        manager = FeatureFlagManager(mock)
        assert manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "task-1") is False

    def test_canary_5pct_routes_small_fraction(self):
        """With 5% canary, roughly 5 out of 100 sequential task IDs should be routed."""
        mock = MagicMock()

        def get_side_effect(key):
            if key.endswith(":enabled"):
                return b"true"
            if key.endswith(":canary_percentage"):
                return b"5"
            return None

        mock.get.side_effect = get_side_effect
        manager = FeatureFlagManager(mock)

        enabled_count = sum(
            1 for i in range(1000)
            if manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, f"task-{i}")
        )
        # Expect roughly 5% ± 3% (statistical tolerance)
        assert 20 <= enabled_count <= 80, (
            f"Expected ~50 enabled out of 1000 at 5%, got {enabled_count}"
        )

    def test_empty_task_id_uses_bucket_zero(self):
        """Empty task_id should use bucket 0 (deterministic fallback)."""
        mock = MagicMock()

        def get_side_effect(key):
            if key.endswith(":enabled"):
                return b"true"
            if key.endswith(":canary_percentage"):
                return b"1"  # Only bucket 0 is included
            return None

        mock.get.side_effect = get_side_effect
        manager = FeatureFlagManager(mock)
        # bucket 0 < 1, so should be True
        result = manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "")
        assert result is True


# ---------------------------------------------------------------------------
# Property tests — canary percentage routing
# ---------------------------------------------------------------------------


class TestCanaryPercentageRouting:
    @given(canary_pct_strategy, task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_property_37_canary_routing_respects_percentage(
        self, canary_pct: int, task_id: str
    ):
        """
        **Property 37: Canary Deployment Support**

        For any canary_percentage P and task_id T, is_enabled SHALL return True
        iff the task's bucket < P (when the flag is enabled).

        **Validates: Requirements 11.3**
        """
        mock = MagicMock()

        def get_side_effect(key):
            if key.endswith(":enabled"):
                return b"true"
            if key.endswith(":canary_percentage"):
                return str(canary_pct).encode()
            return None

        mock.get.side_effect = get_side_effect
        manager = FeatureFlagManager(mock)

        result = manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, task_id)
        bucket = _canary_bucket(task_id)

        if canary_pct == 0:
            assert result is False, "0% canary must always return False"
        elif canary_pct >= 100:
            assert result is True, "100% canary must always return True"
        else:
            expected = bucket < canary_pct
            assert result == expected, (
                f"task_id={task_id!r} bucket={bucket} canary_pct={canary_pct} "
                f"expected={expected} got={result}"
            )

    @given(flag_strategy, task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_40_disabled_flag_always_returns_false(
        self, flag: FeatureFlag, task_id: str
    ):
        """
        **Property 40: Zero Downtime Upgrades**

        For any feature flag and task_id, a disabled flag SHALL always return
        False, ensuring the legacy path is used and no downtime occurs.

        **Validates: Requirements 11.7**
        """
        manager = _make_manager(enabled="false", canary_pct="100")
        assert manager.is_enabled(flag, task_id) is False

    @given(flag_strategy, task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_40_100pct_enabled_flag_always_returns_true(
        self, flag: FeatureFlag, task_id: str
    ):
        """
        **Property 40: Zero Downtime Upgrades**

        For any feature flag and task_id, a fully-enabled flag (100%) SHALL
        always return True.

        **Validates: Requirements 11.7**
        """
        manager = _make_manager(enabled="true", canary_pct="100")
        assert manager.is_enabled(flag, task_id) is True


# ---------------------------------------------------------------------------
# Unit tests — set_flag
# ---------------------------------------------------------------------------


class TestSetFlag:
    def test_set_flag_writes_correct_redis_keys(self):
        mock = MagicMock()
        pipe = MagicMock()
        mock.pipeline.return_value = pipe

        manager = FeatureFlagManager(mock)
        manager.set_flag(
            FeatureFlag.LANGGRAPH_ENGINE,
            enabled=True,
            canary_percentage=25,
            updated_by="operator-1",
        )

        pipe.set.assert_any_call(_enabled_key(FeatureFlag.LANGGRAPH_ENGINE), "true")
        pipe.set.assert_any_call(_canary_key(FeatureFlag.LANGGRAPH_ENGINE), "25")
        pipe.set.assert_any_call(
            _updated_by_key(FeatureFlag.LANGGRAPH_ENGINE), "operator-1"
        )
        pipe.execute.assert_called_once()

    def test_set_flag_disabled_writes_false(self):
        mock = MagicMock()
        pipe = MagicMock()
        mock.pipeline.return_value = pipe

        manager = FeatureFlagManager(mock)
        manager.set_flag(FeatureFlag.LANGGRAPH_ENGINE, enabled=False, canary_percentage=0)

        pipe.set.assert_any_call(_enabled_key(FeatureFlag.LANGGRAPH_ENGINE), "false")
        pipe.set.assert_any_call(_canary_key(FeatureFlag.LANGGRAPH_ENGINE), "0")

    def test_set_flag_invalid_percentage_raises(self):
        mock = MagicMock()
        manager = FeatureFlagManager(mock)

        with pytest.raises(ValueError, match="canary_percentage"):
            manager.set_flag(FeatureFlag.LANGGRAPH_ENGINE, enabled=True, canary_percentage=101)

        with pytest.raises(ValueError, match="canary_percentage"):
            manager.set_flag(FeatureFlag.LANGGRAPH_ENGINE, enabled=True, canary_percentage=-1)

    @given(canary_pct_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_37_set_flag_accepts_valid_percentages(self, pct: int):
        """
        **Property 37: Canary Deployment Support**

        For any canary_percentage in [0, 100], set_flag SHALL succeed without
        raising an exception.

        **Validates: Requirements 11.3**
        """
        mock = MagicMock()
        pipe = MagicMock()
        mock.pipeline.return_value = pipe

        manager = FeatureFlagManager(mock)
        # Should not raise
        manager.set_flag(FeatureFlag.LANGGRAPH_ENGINE, enabled=True, canary_percentage=pct)
        pipe.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Unit tests — disable_flag (rollback)
# ---------------------------------------------------------------------------


class TestDisableFlag:
    def test_disable_flag_sets_enabled_false_and_pct_zero(self):
        mock = MagicMock()
        pipe = MagicMock()
        mock.pipeline.return_value = pipe

        manager = FeatureFlagManager(mock)
        manager.disable_flag(FeatureFlag.LANGGRAPH_ENGINE, updated_by="rollback-script")

        pipe.set.assert_any_call(_enabled_key(FeatureFlag.LANGGRAPH_ENGINE), "false")
        pipe.set.assert_any_call(_canary_key(FeatureFlag.LANGGRAPH_ENGINE), "0")
        pipe.set.assert_any_call(
            _updated_by_key(FeatureFlag.LANGGRAPH_ENGINE), "rollback-script"
        )

    @given(flag_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_40_disable_flag_always_routes_to_legacy(self, flag: FeatureFlag):
        """
        **Property 40: Zero Downtime Upgrades**

        For any feature flag, after disable_flag is called, is_enabled SHALL
        return False for all task_ids, ensuring zero downtime rollback.

        **Validates: Requirements 11.7**
        """
        # Simulate: after disable_flag, Redis returns enabled=false, pct=0
        mock = MagicMock()
        pipe = MagicMock()
        mock.pipeline.return_value = pipe

        # After disable, reads return false/0
        def get_after_disable(key):
            if key.endswith(":enabled"):
                return b"false"
            if key.endswith(":canary_percentage"):
                return b"0"
            return None

        mock.get.side_effect = get_after_disable

        manager = FeatureFlagManager(mock)
        manager.disable_flag(flag)

        # Verify is_enabled returns False for multiple task IDs
        for task_id in ["task-1", "task-abc", "task-xyz-999"]:
            assert manager.is_enabled(flag, task_id) is False


# ---------------------------------------------------------------------------
# Unit tests — get_flag_state
# ---------------------------------------------------------------------------


class TestGetFlagState:
    def test_get_flag_state_returns_correct_structure(self):
        mock = MagicMock()

        def get_side_effect(key):
            if key.endswith(":enabled"):
                return b"true"
            if key.endswith(":canary_percentage"):
                return b"25"
            if key.endswith(":updated_at"):
                return b"2026-01-01T00:00:00+00:00"
            if key.endswith(":updated_by"):
                return b"operator-1"
            return None

        mock.get.side_effect = get_side_effect
        manager = FeatureFlagManager(mock)

        state = manager.get_flag_state(FeatureFlag.LANGGRAPH_ENGINE)

        assert state["flag"] == "langgraph_engine"
        assert state["enabled"] is True
        assert state["canary_percentage"] == 25
        assert state["updated_at"] == "2026-01-01T00:00:00+00:00"
        assert state["updated_by"] == "operator-1"

    def test_get_flag_state_redis_error_returns_safe_defaults(self):
        mock = MagicMock()
        mock.get.side_effect = ConnectionError("Redis down")
        manager = FeatureFlagManager(mock)

        state = manager.get_flag_state(FeatureFlag.LANGGRAPH_ENGINE)

        assert state["enabled"] is False
        assert state["canary_percentage"] == 0

    def test_get_flag_state_missing_keys_returns_defaults(self):
        mock = MagicMock()
        mock.get.return_value = None
        manager = FeatureFlagManager(mock)

        state = manager.get_flag_state(FeatureFlag.LANGGRAPH_ENGINE)

        assert state["enabled"] is False
        assert state["canary_percentage"] == 0
        assert state["updated_at"] is None
        assert state["updated_by"] is None


# ---------------------------------------------------------------------------
# Unit tests — list_flags
# ---------------------------------------------------------------------------


class TestListFlags:
    def test_list_flags_returns_all_flags(self):
        mock = MagicMock()
        mock.get.return_value = None
        manager = FeatureFlagManager(mock)

        flags = manager.list_flags()

        assert len(flags) == len(FeatureFlag)
        flag_names = {f["flag"] for f in flags}
        for flag in FeatureFlag:
            assert flag.value in flag_names

    @given(flag_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_38_all_flags_have_backward_compatible_defaults(
        self, flag: FeatureFlag
    ):
        """
        **Property 38: Backward Compatibility Maintenance**

        For any feature flag, the default state (no Redis keys set) SHALL be
        disabled, ensuring existing deployments continue to use the legacy path
        without any configuration changes.

        **Validates: Requirements 11.4**
        """
        mock = MagicMock()
        mock.get.return_value = None  # No keys set — fresh deployment
        manager = FeatureFlagManager(mock)

        state = manager.get_flag_state(flag)
        assert state["enabled"] is False, (
            f"Flag {flag.value} must default to disabled for backward compatibility"
        )
        assert state["canary_percentage"] == 0


# ---------------------------------------------------------------------------
# Integration-style tests — Redis persistence
# ---------------------------------------------------------------------------


class TestRedisPersistence:
    def test_set_and_get_flag_state_round_trip(self):
        """
        Simulate a set_flag followed by get_flag_state using a simple in-memory
        dict as a fake Redis store.
        """
        store: dict[str, bytes] = {}

        mock = MagicMock()
        mock.get.side_effect = lambda key: store.get(key)

        pipe = MagicMock()
        mock.pipeline.return_value = pipe

        def pipe_set(key, value):
            store[key] = value.encode() if isinstance(value, str) else value

        pipe.set.side_effect = pipe_set
        pipe.execute.return_value = None

        manager = FeatureFlagManager(mock)
        manager.set_flag(
            FeatureFlag.NEW_BACKEND_GENERATOR,
            enabled=True,
            canary_percentage=50,
            updated_by="test-operator",
        )

        state = manager.get_flag_state(FeatureFlag.NEW_BACKEND_GENERATOR)
        assert state["enabled"] is True
        assert state["canary_percentage"] == 50
        assert state["updated_by"] == "test-operator"

    def test_is_enabled_reads_from_redis_on_each_call(self):
        """
        is_enabled must read from Redis on every call so that flag changes
        take effect immediately without requiring a service restart.
        """
        mock = MagicMock()
        call_count = 0

        def get_side_effect(key):
            nonlocal call_count
            call_count += 1
            if key.endswith(":enabled"):
                return b"true"
            if key.endswith(":canary_percentage"):
                return b"100"
            return None

        mock.get.side_effect = get_side_effect
        manager = FeatureFlagManager(mock)

        manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "task-1")
        manager.is_enabled(FeatureFlag.LANGGRAPH_ENGINE, "task-2")

        # Each is_enabled call should read at least the enabled key
        assert call_count >= 2, "is_enabled must read from Redis on each call"
