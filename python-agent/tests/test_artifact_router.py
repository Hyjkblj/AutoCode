"""
Tests for ArtifactRouter canary deployment routing.

Task 30.3: Implement gradual migration with canary deployment
Validates: Requirements 11.3, 11.6, 11.7

Property 37: Canary Deployment Support
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from utils.artifact_router import ArtifactRouter
from utils.feature_flags import FeatureFlag, FeatureFlagManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_router(flag_enabled: bool = False, canary_pct: int = 0) -> ArtifactRouter:
    """Return an ArtifactRouter with a mocked FeatureFlagManager."""
    mock_redis = MagicMock()

    def get_side_effect(key: str):
        if key.endswith(":enabled"):
            return b"true" if flag_enabled else b"false"
        if key.endswith(":canary_percentage"):
            return str(canary_pct).encode()
        return None

    mock_redis.get.side_effect = get_side_effect
    manager = FeatureFlagManager(mock_redis)
    return ArtifactRouter(
        manager,
        control_plane_url="http://control-plane:8058",
        artifact_service_url="http://artifact-service:8081",
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestArtifactRouterDisabled:
    """When ARTIFACT_MICROSERVICE flag is disabled, all traffic goes to Control Plane."""

    def test_get_artifact_base_url_returns_control_plane(self):
        router = _make_router(flag_enabled=False)
        url = router.get_artifact_base_url("task-1")
        assert url == "http://control-plane:8058"

    def test_get_artifact_upload_url_uses_control_plane_path(self):
        router = _make_router(flag_enabled=False)
        url = router.get_artifact_upload_url("task-1")
        assert "control-plane:8058" in url
        assert "task-1" in url

    def test_get_artifact_download_url_uses_control_plane_path(self):
        router = _make_router(flag_enabled=False)
        url = router.get_artifact_download_url("task-1", "art-abc")
        assert "control-plane:8058" in url
        assert "art-abc" in url

    def test_is_using_microservice_returns_false(self):
        router = _make_router(flag_enabled=False)
        assert router.is_using_microservice("task-1") is False


class TestArtifactRouterEnabled:
    """When ARTIFACT_MICROSERVICE flag is enabled at 100%, all traffic goes to microservice."""

    def test_get_artifact_base_url_returns_artifact_service(self):
        router = _make_router(flag_enabled=True, canary_pct=100)
        url = router.get_artifact_base_url("task-1")
        assert url == "http://artifact-service:8081"

    def test_get_artifact_upload_url_uses_artifact_service_path(self):
        router = _make_router(flag_enabled=True, canary_pct=100)
        url = router.get_artifact_upload_url("task-1")
        assert "artifact-service:8081" in url
        assert "/artifacts" in url

    def test_get_artifact_download_url_uses_artifact_service_path(self):
        router = _make_router(flag_enabled=True, canary_pct=100)
        url = router.get_artifact_download_url("task-1", "art-abc")
        assert "artifact-service:8081" in url
        assert "art-abc" in url

    def test_is_using_microservice_returns_true(self):
        router = _make_router(flag_enabled=True, canary_pct=100)
        assert router.is_using_microservice("task-1") is True


class TestArtifactRouterCanary:
    """Canary routing distributes traffic based on task_id hash."""

    def test_same_task_id_always_routes_to_same_service(self):
        router = _make_router(flag_enabled=True, canary_pct=50)
        url1 = router.get_artifact_base_url("stable-task-id")
        url2 = router.get_artifact_base_url("stable-task-id")
        assert url1 == url2

    def test_zero_percent_canary_always_routes_to_control_plane(self):
        router = _make_router(flag_enabled=True, canary_pct=0)
        for i in range(20):
            url = router.get_artifact_base_url(f"task-{i}")
            assert "control-plane:8058" in url

    def test_hundred_percent_canary_always_routes_to_microservice(self):
        router = _make_router(flag_enabled=True, canary_pct=100)
        for i in range(20):
            url = router.get_artifact_base_url(f"task-{i}")
            assert "artifact-service:8081" in url

    def test_fifty_percent_canary_distributes_traffic(self):
        router = _make_router(flag_enabled=True, canary_pct=50)
        microservice_count = sum(
            1 for i in range(200)
            if router.is_using_microservice(f"task-{i}")
        )
        # Expect roughly 50% ± 15%
        assert 70 <= microservice_count <= 130, (
            f"Expected ~100 out of 200 at 50% canary, got {microservice_count}"
        )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

_task_id_strategy = st.text(
    min_size=1,
    max_size=64,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)


class TestProperty37CanaryDeploymentSupport:
    """
    **Property 37: Canary Deployment Support**

    For any feature flag and task_id, routing is deterministic and consistent.

    **Validates: Requirements 11.3**
    """

    @given(_task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_37_routing_is_deterministic(self, task_id: str) -> None:
        """
        For any task_id, get_artifact_base_url() SHALL return the same URL
        on repeated calls (deterministic routing).

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=50)
        url1 = router.get_artifact_base_url(task_id)
        url2 = router.get_artifact_base_url(task_id)
        assert url1 == url2, (
            f"Routing must be deterministic for task_id={task_id!r}: "
            f"got {url1!r} then {url2!r}"
        )

    @given(_task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_37_disabled_flag_always_routes_to_control_plane(
        self, task_id: str
    ) -> None:
        """
        For any task_id, when the flag is disabled, routing SHALL always
        go to the Control Plane (zero downtime rollback).

        **Validates: Requirements 11.3, 11.7**
        """
        router = _make_router(flag_enabled=False)
        url = router.get_artifact_base_url(task_id)
        assert "control-plane:8058" in url, (
            f"Disabled flag must route to control-plane for task_id={task_id!r}"
        )

    @given(_task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_37_100pct_flag_always_routes_to_microservice(
        self, task_id: str
    ) -> None:
        """
        For any task_id, when the flag is enabled at 100%, routing SHALL
        always go to the artifact microservice.

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=100)
        url = router.get_artifact_base_url(task_id)
        assert "artifact-service:8081" in url, (
            f"100% flag must route to artifact-service for task_id={task_id!r}"
        )

    @given(_task_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_37_url_is_always_non_empty(self, task_id: str) -> None:
        """
        For any task_id and any flag state, get_artifact_base_url() SHALL
        always return a non-empty string.

        **Validates: Requirements 11.3**
        """
        router = _make_router(flag_enabled=True, canary_pct=50)
        url = router.get_artifact_base_url(task_id)
        assert isinstance(url, str) and len(url) > 0
