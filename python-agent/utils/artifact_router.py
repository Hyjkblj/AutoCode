"""
Artifact service routing with canary deployment support.

Routes artifact API calls to either the Control Plane monolith or the
standalone artifact-service microservice based on the ARTIFACT_MICROSERVICE
feature flag.

**Validates: Requirements 11.3, 11.6, 11.7**
"""
from __future__ import annotations

import logging
from typing import Any

from utils.feature_flags import FeatureFlag, FeatureFlagManager

logger = logging.getLogger(__name__)

# Default service URLs
_DEFAULT_CONTROL_PLANE_URL = "http://localhost:8058"
_DEFAULT_ARTIFACT_SERVICE_URL = "http://localhost:8081"


class ArtifactRouter:
    """
    Routes artifact requests to the appropriate backend service based on the
    ARTIFACT_MICROSERVICE feature flag.

    When the flag is disabled (default), all requests go to the Control Plane
    monolith. When enabled, requests are routed to the standalone
    artifact-service microservice based on the canary percentage.

    **Validates: Requirements 11.3, 11.6, 11.7**
    """

    def __init__(
        self,
        feature_flag_manager: FeatureFlagManager,
        *,
        control_plane_url: str = _DEFAULT_CONTROL_PLANE_URL,
        artifact_service_url: str = _DEFAULT_ARTIFACT_SERVICE_URL,
    ) -> None:
        self._flags = feature_flag_manager
        self._control_plane_url = control_plane_url.rstrip("/")
        self._artifact_service_url = artifact_service_url.rstrip("/")

    def get_artifact_base_url(self, task_id: str) -> str:
        """
        Return the base URL for artifact API calls for the given task.

        Uses the ARTIFACT_MICROSERVICE feature flag to determine routing.
        The same task_id always routes to the same service (consistent hash).

        Parameters
        ----------
        task_id:
            The task identifier used for canary bucket assignment.

        Returns
        -------
        str
            Base URL of the service to use for artifact operations.

        **Validates: Requirements 11.3**
        """
        use_microservice = self._flags.is_enabled(
            FeatureFlag.ARTIFACT_MICROSERVICE, task_id
        )
        if use_microservice:
            logger.debug(
                "ArtifactRouter: routing task_id=%s to artifact-service (%s)",
                task_id,
                self._artifact_service_url,
            )
            return self._artifact_service_url
        else:
            logger.debug(
                "ArtifactRouter: routing task_id=%s to control-plane (%s)",
                task_id,
                self._control_plane_url,
            )
            return self._control_plane_url

    def get_artifact_upload_url(self, task_id: str) -> str:
        """Return the URL for uploading an artifact for the given task."""
        base = self.get_artifact_base_url(task_id)
        if self._flags.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id):
            # artifact-service uses /artifacts endpoint
            return f"{base}/artifacts"
        else:
            # Control Plane uses /api/v1/tasks/{taskId}/artifacts
            return f"{base}/api/v1/tasks/{task_id}/artifacts"

    def get_artifact_download_url(self, task_id: str, artifact_id: str) -> str:
        """Return the URL for downloading a specific artifact."""
        base = self.get_artifact_base_url(task_id)
        if self._flags.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id):
            return f"{base}/artifacts/{artifact_id}/download?taskId={task_id}"
        else:
            return f"{base}/api/v1/tasks/{task_id}/artifacts/{artifact_id}/download"

    def is_using_microservice(self, task_id: str) -> bool:
        """Return True if the given task is routed to the artifact microservice."""
        return self._flags.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id)
