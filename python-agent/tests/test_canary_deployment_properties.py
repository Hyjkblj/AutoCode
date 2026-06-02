"""
Property-based tests for canary deployment support.

Task 30.4: Write property tests for microservice functionality
Property 37: Canary Deployment Support
Validates: Requirements 11.3

These tests validate that "THE system SHALL support gradual rollout with canary
deployment capabilities" — specifically that routing is deterministic, bounded,
and consistent between FeatureFlagManager and ArtifactRouter.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from utils.artifact_router import ArtifactRouter
from utils.feature_flags import FeatureFlag, FeatureFlagManager, _canary_bucket


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Any non-empty string up to 128 chars is a valid task_id
task_id_strategy = st.text(
    min_size=1,
    max_size=128,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
)

# Canary percentage in the valid range [0, 100]
canary_pct_strategy = st.integers(min_value=0, max_value=100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(flag_enabled: bool, canary_pct: int) -> FeatureFlagManager:
    """Return a FeatureFlagManager backed by an isolated Redis mock."""
    mock_redis = MagicMock()

    def _get(key: str):
        if key.endswith(":enabled"):
            return b"true" if flag_enabled else b"false"
        if key.endswith(":canary_percentage"):
            return str(canary_pct).encode()
        return None

    mock_redis.get.side_effect = _get
    return FeatureFlagManager(mock_redis)


def _make_router(flag_enabled: bool, canary_pct: int) -> ArtifactRouter:
    """Return an ArtifactRouter with an isolated Redis mock."""
    manager = _make_manager(flag_enabled, canary_pct)
    return ArtifactRouter(
        manager,
        control_plane_url="http://control-plane:8058",
        artifact_service_url="http://artifact-service:8081",
    )


# ---------------------------------------------------------------------------
# Property 37a: Canary bucket is always in [0, 99]
# ---------------------------------------------------------------------------

class TestProperty37aCanaryBucketRange:
    """
    **Property 37a: Canary bucket is always in [0, 99]**

    For any task_id, _canary_bucket(task_id) SHALL return a value in [0, 99].

    **Validates: Requirements 11.3**
    """

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_canary_bucket_always_in_range(self, task_id: str) -> None:
        """
        For any task_id, _canary_bucket(task_id) is always in [0, 99].

        **Validates: Requirements 11.3**
        """
        bucket = _canary_bucket(task_id)
        assert 0 <= bucket <= 99, (
            f"_canary_bucket({task_id!r}) returned {bucket}, expected [0, 99]"
        )

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_canary_bucket_is_integer(self, task_id: str) -> None:
        """
        For any task_id, _canary_bucket(task_id) returns an integer.

        **Validates: Requirements 11.3**
        """
        bucket = _canary_bucket(task_id)
        assert isinstance(bucket, int), (
            f"_canary_bucket({task_id!r}) returned {type(bucket)}, expected int"
        )


# ---------------------------------------------------------------------------
# Property 37b: Canary routing is deterministic
# ---------------------------------------------------------------------------

class TestProperty37bDeterministicRouting:
    """
    **Property 37b: Canary routing is deterministic**

    For any task_id and canary_percentage, is_enabled() returns the same value
    on repeated calls.

    **Validates: Requirements 11.3**
    """

    @given(task_id_strategy, canary_pct_strategy)
    @settings(max_examples=200, deadline=None)
    def test_is_enabled_is_deterministic(self, task_id: str, canary_pct: int) -> None:
        """
        For any task_id and canary_percentage, is_enabled() returns the same
        value on repeated calls (deterministic routing).

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=canary_pct)
        result1 = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        result2 = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        assert result1 == result2, (
            f"is_enabled() is not deterministic for task_id={task_id!r}, "
            f"canary_pct={canary_pct}: got {result1} then {result2}"
        )

    @given(task_id_strategy, canary_pct_strategy)
    @settings(max_examples=200, deadline=None)
    def test_canary_bucket_is_deterministic(self, task_id: str, canary_pct: int) -> None:
        """
        For any task_id, _canary_bucket() returns the same value on repeated calls.

        **Validates: Requirements 11.3**
        """
        bucket1 = _canary_bucket(task_id)
        bucket2 = _canary_bucket(task_id)
        assert bucket1 == bucket2, (
            f"_canary_bucket({task_id!r}) is not deterministic: "
            f"got {bucket1} then {bucket2}"
        )

    @given(task_id_strategy, canary_pct_strategy)
    @settings(max_examples=200, deadline=None)
    def test_router_routing_is_deterministic(self, task_id: str, canary_pct: int) -> None:
        """
        For any task_id, ArtifactRouter.is_using_microservice() returns the same
        value on repeated calls.

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=canary_pct)
        result1 = router.is_using_microservice(task_id)
        result2 = router.is_using_microservice(task_id)
        assert result1 == result2, (
            f"is_using_microservice() is not deterministic for task_id={task_id!r}, "
            f"canary_pct={canary_pct}: got {result1} then {result2}"
        )


# ---------------------------------------------------------------------------
# Property 37c: Zero percent canary never routes to new service
# ---------------------------------------------------------------------------

class TestProperty37cZeroPercentCanary:
    """
    **Property 37c: Zero percent canary never routes to new service**

    For any task_id, is_enabled(flag, task_id) with canary_percentage=0 always
    returns False.

    **Validates: Requirements 11.3**
    """

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_zero_percent_canary_never_enabled(self, task_id: str) -> None:
        """
        For any task_id, is_enabled() with canary_percentage=0 always returns False.

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=0)
        result = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        assert result is False, (
            f"is_enabled() with canary_pct=0 returned True for task_id={task_id!r}"
        )

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_zero_percent_router_always_legacy(self, task_id: str) -> None:
        """
        For any task_id, ArtifactRouter with canary_percentage=0 always routes
        to the legacy control plane.

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=0)
        assert router.is_using_microservice(task_id) is False, (
            f"Router with canary_pct=0 routed to microservice for task_id={task_id!r}"
        )
        url = router.get_artifact_base_url(task_id)
        assert "control-plane:8058" in url, (
            f"Router with canary_pct=0 returned non-legacy URL for task_id={task_id!r}: {url}"
        )


# ---------------------------------------------------------------------------
# Property 37d: 100 percent canary always routes to new service
# ---------------------------------------------------------------------------

class TestProperty37dHundredPercentCanary:
    """
    **Property 37d: 100 percent canary always routes to new service**

    For any task_id, is_enabled(flag, task_id) with canary_percentage=100 always
    returns True.

    **Validates: Requirements 11.3**
    """

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_hundred_percent_canary_always_enabled(self, task_id: str) -> None:
        """
        For any task_id, is_enabled() with canary_percentage=100 always returns True.

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=100)
        result = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        assert result is True, (
            f"is_enabled() with canary_pct=100 returned False for task_id={task_id!r}"
        )

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_hundred_percent_router_always_microservice(self, task_id: str) -> None:
        """
        For any task_id, ArtifactRouter with canary_percentage=100 always routes
        to the artifact microservice.

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=100)
        assert router.is_using_microservice(task_id) is True, (
            f"Router with canary_pct=100 routed to legacy for task_id={task_id!r}"
        )
        url = router.get_artifact_base_url(task_id)
        assert "artifact-service:8081" in url, (
            f"Router with canary_pct=100 returned non-microservice URL for task_id={task_id!r}: {url}"
        )


# ---------------------------------------------------------------------------
# Property 37e: ArtifactRouter routing is consistent with feature flag
# ---------------------------------------------------------------------------

class TestProperty37eRouterConsistencyWithFlag:
    """
    **Property 37e: ArtifactRouter routing is consistent with feature flag**

    For any task_id, ArtifactRouter.is_using_microservice(task_id) matches
    FeatureFlagManager.is_enabled(ARTIFACT_MICROSERVICE, task_id).

    **Validates: Requirements 11.3**
    """

    @given(task_id_strategy, canary_pct_strategy)
    @settings(max_examples=200, deadline=None)
    def test_router_matches_feature_flag(self, task_id: str, canary_pct: int) -> None:
        """
        For any task_id and canary_percentage, ArtifactRouter.is_using_microservice()
        SHALL match FeatureFlagManager.is_enabled(ARTIFACT_MICROSERVICE, task_id).

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=canary_pct)
        router = ArtifactRouter(
            manager,
            control_plane_url="http://control-plane:8058",
            artifact_service_url="http://artifact-service:8081",
        )

        flag_result = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        router_result = router.is_using_microservice(task_id)

        assert flag_result == router_result, (
            f"Router result ({router_result}) does not match feature flag result "
            f"({flag_result}) for task_id={task_id!r}, canary_pct={canary_pct}"
        )

    @given(task_id_strategy, canary_pct_strategy)
    @settings(max_examples=200, deadline=None)
    def test_router_url_matches_flag_decision(self, task_id: str, canary_pct: int) -> None:
        """
        For any task_id, the base URL returned by ArtifactRouter SHALL correspond
        to the service selected by the feature flag.

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=canary_pct)
        router = ArtifactRouter(
            manager,
            control_plane_url="http://control-plane:8058",
            artifact_service_url="http://artifact-service:8081",
        )

        use_microservice = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        url = router.get_artifact_base_url(task_id)

        if use_microservice:
            assert "artifact-service:8081" in url, (
                f"Flag says microservice but URL is {url!r} for task_id={task_id!r}"
            )
        else:
            assert "control-plane:8058" in url, (
                f"Flag says legacy but URL is {url!r} for task_id={task_id!r}"
            )


# ---------------------------------------------------------------------------
# Property 37f: Rollback (disable flag) always routes to legacy
# ---------------------------------------------------------------------------

class TestProperty37fRollbackAlwaysLegacy:
    """
    **Property 37f: Rollback (disable flag) always routes to legacy**

    For any task_id, after disable_flag(ARTIFACT_MICROSERVICE),
    is_using_microservice(task_id) always returns False.

    **Validates: Requirements 11.3**
    """

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_disabled_flag_always_routes_to_legacy(self, task_id: str) -> None:
        """
        For any task_id, when the flag is disabled, is_using_microservice()
        always returns False (zero-downtime rollback).

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=False, canary_pct=0)
        assert router.is_using_microservice(task_id) is False, (
            f"Disabled flag routed to microservice for task_id={task_id!r}"
        )

    @given(task_id_strategy, canary_pct_strategy)
    @settings(max_examples=200, deadline=None)
    def test_disable_flag_overrides_any_canary_pct(
        self, task_id: str, canary_pct: int
    ) -> None:
        """
        For any task_id and any canary_percentage, when the master enabled switch
        is False, is_enabled() always returns False regardless of canary_percentage.

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=False, canary_pct=canary_pct)
        result = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
        assert result is False, (
            f"Disabled flag returned True for task_id={task_id!r}, "
            f"canary_pct={canary_pct}"
        )

    @given(task_id_strategy)
    @settings(max_examples=200, deadline=None)
    def test_disable_flag_url_is_always_control_plane(self, task_id: str) -> None:
        """
        For any task_id, when the flag is disabled, get_artifact_base_url()
        always returns the control-plane URL.

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=False, canary_pct=0)
        url = router.get_artifact_base_url(task_id)
        assert "control-plane:8058" in url, (
            f"Disabled flag returned non-legacy URL {url!r} for task_id={task_id!r}"
        )

    def test_disable_flag_via_manager_method(self) -> None:
        """
        After calling disable_flag() on the manager, is_enabled() returns False
        for any task_id (simulated via mock pipeline).

        **Validates: Requirements 11.3**
        """
        mock_redis = MagicMock()
        # Simulate pipeline execution
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.__enter__ = MagicMock(return_value=mock_pipe)
        mock_pipe.__exit__ = MagicMock(return_value=False)

        # After disable_flag, the manager writes enabled=false
        call_count = [0]

        def _get_after_disable(key: str):
            if key.endswith(":enabled"):
                return b"false"
            if key.endswith(":canary_percentage"):
                return b"0"
            return None

        mock_redis.get.side_effect = _get_after_disable

        manager = FeatureFlagManager(mock_redis)
        manager.disable_flag(FeatureFlag.ARTIFACT_MICROSERVICE)

        # Verify that after disable, is_enabled returns False for various task_ids
        for task_id in ["task-1", "task-abc", "task-xyz-999", "a", "Z"]:
            result = manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
            assert result is False, (
                f"After disable_flag, is_enabled returned True for task_id={task_id!r}"
            )


# ---------------------------------------------------------------------------
# Property 37g: Traffic distribution is approximately correct
# ---------------------------------------------------------------------------

class TestProperty37gTrafficDistribution:
    """
    **Property 37g: Traffic distribution is approximately correct**

    For 1000 task IDs with 50% canary, approximately 50% route to microservice
    (within ±10%).

    **Validates: Requirements 11.3**
    """

    def test_fifty_percent_canary_distributes_traffic_approximately(self) -> None:
        """
        For 1000 task IDs with 50% canary, approximately 50% route to microservice
        (within ±10%).

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=50)
        n = 1000
        microservice_count = sum(
            1
            for i in range(n)
            if manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, f"task-{i}")
        )
        ratio = microservice_count / n
        assert 0.40 <= ratio <= 0.60, (
            f"50% canary distributed {microservice_count}/{n} ({ratio:.1%}) to "
            f"microservice; expected 40%–60%"
        )

    def test_twenty_percent_canary_distributes_traffic_approximately(self) -> None:
        """
        For 1000 task IDs with 20% canary, approximately 20% route to microservice
        (within ±10%).

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=20)
        n = 1000
        microservice_count = sum(
            1
            for i in range(n)
            if manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, f"task-{i}")
        )
        ratio = microservice_count / n
        assert 0.10 <= ratio <= 0.30, (
            f"20% canary distributed {microservice_count}/{n} ({ratio:.1%}) to "
            f"microservice; expected 10%–30%"
        )

    def test_router_fifty_percent_canary_distributes_traffic_approximately(self) -> None:
        """
        For 1000 task IDs with 50% canary, ArtifactRouter routes approximately
        50% to microservice (within ±10%).

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=50)
        n = 1000
        microservice_count = sum(
            1
            for i in range(n)
            if router.is_using_microservice(f"task-{i}")
        )
        ratio = microservice_count / n
        assert 0.40 <= ratio <= 0.60, (
            f"50% canary router distributed {microservice_count}/{n} ({ratio:.1%}) to "
            f"microservice; expected 40%–60%"
        )

    @given(st.integers(min_value=1, max_value=99))
    @settings(max_examples=20, deadline=None)
    def test_canary_percentage_monotonically_increases_traffic(
        self, canary_pct: int
    ) -> None:
        """
        For any canary_percentage p in (0, 100), the fraction of task IDs routed
        to the microservice SHALL be approximately p/100 (within ±15%).

        **Validates: Requirements 11.3**
        """
        manager = _make_manager(flag_enabled=True, canary_pct=canary_pct)
        n = 500
        microservice_count = sum(
            1
            for i in range(n)
            if manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, f"task-{i}")
        )
        ratio = microservice_count / n
        expected = canary_pct / 100
        assert abs(ratio - expected) <= 0.15, (
            f"canary_pct={canary_pct}: got {microservice_count}/{n} ({ratio:.1%}), "
            f"expected ~{expected:.1%} (±15%)"
        )
