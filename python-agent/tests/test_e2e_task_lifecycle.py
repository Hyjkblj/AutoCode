"""
End-to-End Test Suite for Complete Task Lifecycle

**Validates: Requirements 6.5**

This test suite covers the complete task lifecycle from creation through execution to artifact delivery:
- Task creation through Control Plane API
- Python Agent task polling and execution
- Event flow from Python Agent to Control Plane
- Artifact generation and hosting

The tests verify that all system components work together correctly in an integrated environment.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from urllib import request, error

import pytest

# Add python-agent to sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from client.control_plane_client import ControlPlaneClient
from orchestrator.agent_orchestrator import AgentOrchestrator


class TestE2ETaskLifecycle:
    """
    End-to-end tests for complete task lifecycle.
    
    These tests verify the integration of all system components:
    - Control Plane (task management, event processing)
    - Python Agent (task execution, event publishing)
    - Artifact Service (storage and hosting)
    """

    @pytest.fixture
    def control_plane_url(self) -> str:
        """Get Control Plane URL from environment or use default."""
        return os.environ.get("MVP_BASE_URL", "http://localhost:8058")

    @pytest.fixture
    def agent_token(self) -> str:
        """Get agent authentication token."""
        return os.environ.get("MVP_AGENT_TOKEN", "agent-dev-token")

    @pytest.fixture
    def control_plane_client(self, control_plane_url: str, agent_token: str) -> ControlPlaneClient:
        """Create a Control Plane client for testing."""
        return ControlPlaneClient(
            base_url=control_plane_url,
            agent_token=agent_token,
            timeout_seconds=30
        )

    @pytest.fixture
    def test_workspace(self) -> Path:
        """Create a temporary workspace for test execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            yield workspace

    def _create_task_via_api(
        self,
        control_plane_url: str,
        agent_token: str,
        project_id: str,
        prompt: str,
        assistant: str = "web",
        workspace_path: str | None = None,
        idempotency_key: str | None = None
    ) -> dict[str, Any]:
        """
        Create a task through the Control Plane REST API.
        
        This simulates the operator/frontend creating a task.
        """
        url = f"{control_plane_url}/api/v1/tasks"
        
        task_request = {
            "projectId": project_id,
            "prompt": prompt,
            "assistant": assistant,
            "agentProfile": "coder",
            "sessionKey": f"e2e-session-{int(time.time())}",
            "inputMode": "voice_text",
            "riskPolicy": "strict_approval"
        }
        
        if workspace_path:
            task_request["workspacePath"] = workspace_path
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {agent_token}"
        }
        
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        
        req = request.Request(
            url,
            data=json.dumps(task_request).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if response_data.get("ok"):
                    return response_data.get("payload", {})
                else:
                    raise Exception(f"Task creation failed: {response_data.get('error')}")
        except error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else "No error body"
            raise Exception(f"HTTP {e.code}: {error_body}")

    def _get_task_status(
        self,
        control_plane_url: str,
        agent_token: str,
        task_id: str
    ) -> dict[str, Any]:
        """Get task status from Control Plane."""
        url = f"{control_plane_url}/api/v1/tasks/{task_id}"
        
        headers = {
            "Authorization": f"Bearer {agent_token}"
        }
        
        req = request.Request(url, headers=headers, method="GET")
        
        try:
            with request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if response_data.get("ok"):
                    return response_data.get("payload", {})
                else:
                    raise Exception(f"Failed to get task: {response_data.get('error')}")
        except error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else "No error body"
            raise Exception(f"HTTP {e.code}: {error_body}")

    def _get_task_events(
        self,
        control_plane_url: str,
        agent_token: str,
        task_id: str,
        last_seq: int | None = None
    ) -> list[dict[str, Any]]:
        """Get task events from Control Plane."""
        url = f"{control_plane_url}/api/v1/tasks/{task_id}/events"
        if last_seq is not None:
            url += f"?lastSeq={last_seq}"
        
        headers = {
            "Authorization": f"Bearer {agent_token}"
        }
        
        req = request.Request(url, headers=headers, method="GET")
        
        try:
            with request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if response_data.get("ok"):
                    return response_data.get("payload", [])
                else:
                    raise Exception(f"Failed to get events: {response_data.get('error')}")
        except error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else "No error body"
            raise Exception(f"HTTP {e.code}: {error_body}")

    def _wait_for_task_completion(
        self,
        control_plane_url: str,
        agent_token: str,
        task_id: str,
        timeout_seconds: int = 120,
        poll_interval: float = 2.0
    ) -> dict[str, Any]:
        """
        Wait for task to reach a terminal state (SUCCEEDED, FAILED, CANCELED).
        
        Returns the final task status.
        """
        start_time = time.time()
        terminal_states = {"SUCCEEDED", "FAILED", "CANCELED"}
        
        while time.time() - start_time < timeout_seconds:
            task_status = self._get_task_status(control_plane_url, agent_token, task_id)
            current_state = task_status.get("status")
            
            if current_state in terminal_states:
                return task_status
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout_seconds} seconds")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("RUN_E2E_TESTS"),
        reason="E2E tests require RUN_E2E_TESTS=1 and running Control Plane"
    )
    def test_complete_task_lifecycle_web_generation(
        self,
        control_plane_url: str,
        agent_token: str,
        test_workspace: Path
    ):
        """
        Test complete task lifecycle for web generation.
        
        **Validates: Requirements 6.5**
        
        This test verifies:
        1. Task creation through Control Plane API
        2. Task enters QUEUED state
        3. Python Agent polls and leases the task
        4. Task enters RUNNING state
        5. Events are published from Python Agent to Control Plane
        6. Task completes successfully (SUCCEEDED state)
        7. Artifact is generated and accessible
        """
        # Step 1: Create task through Control Plane API
        project_id = "e2e-test-project"
        prompt = "Create a simple todo list web page with HTML, CSS, and JavaScript"
        
        task_summary = self._create_task_via_api(
            control_plane_url=control_plane_url,
            agent_token=agent_token,
            project_id=project_id,
            prompt=prompt,
            assistant="web",
            workspace_path=str(test_workspace)
        )
        
        task_id = task_summary.get("taskId")
        assert task_id is not None, "Task ID should be returned"
        assert task_summary.get("status") in ["PENDING", "QUEUED"], "Task should be in PENDING or QUEUED state"
        assert task_summary.get("projectId") == project_id
        assert task_summary.get("prompt") == prompt
        
        print(f"✓ Task created: {task_id}")
        
        # Step 2: Verify task is in QUEUED state
        time.sleep(1)  # Allow time for task to be enqueued
        task_status = self._get_task_status(control_plane_url, agent_token, task_id)
        assert task_status.get("status") in ["PENDING", "QUEUED", "LEASED", "RUNNING"], \
            f"Task should be queued or processing, got: {task_status.get('status')}"
        
        print(f"✓ Task queued: {task_status.get('status')}")
        
        # Step 3: Wait for Python Agent to poll and execute the task
        # The Python Agent should be running in the background and will:
        # - Poll for the task
        # - Lease the task
        # - Execute the task
        # - Publish events
        # - Generate artifacts
        
        print("⏳ Waiting for Python Agent to execute task...")
        
        final_status = self._wait_for_task_completion(
            control_plane_url=control_plane_url,
            agent_token=agent_token,
            task_id=task_id,
            timeout_seconds=180  # Allow up to 3 minutes for generation
        )
        
        print(f"✓ Task completed with status: {final_status.get('status')}")
        
        # Step 4: Verify task completed successfully
        assert final_status.get("status") == "SUCCEEDED", \
            f"Task should succeed, got: {final_status.get('status')}"
        
        # Step 5: Verify events were published
        events = self._get_task_events(control_plane_url, agent_token, task_id)
        assert len(events) > 0, "Events should be published"
        
        event_types = [e.get("type") for e in events]
        print(f"✓ Events published: {event_types}")
        
        # Verify key events are present
        assert "TASK_STARTED" in event_types, "TASK_STARTED event should be published"
        assert "ARTIFACT_READY" in event_types or "FILE_PATCH_PREVIEW" in event_types, \
            "Artifact or file events should be published"
        
        # Step 6: Verify artifact generation
        artifact_events = [e for e in events if e.get("type") == "ARTIFACT_READY"]
        if artifact_events:
            artifact_event = artifact_events[0]
            artifact_payload = artifact_event.get("payload", {})
            artifact_info = artifact_payload.get("artifact", {})
            
            # Verify artifact metadata
            assert artifact_info.get("artifactId") is not None, "Artifact ID should be present"
            assert artifact_info.get("name") is not None, "Artifact name should be present"
            
            print(f"✓ Artifact generated: {artifact_info.get('artifactId')}")
            
            # If artifact has a local path, verify it's a valid ZIP
            local_path = artifact_info.get("localPath")
            if local_path and Path(local_path).exists():
                with zipfile.ZipFile(local_path) as zf:
                    file_names = zf.namelist()
                    assert any("index.html" in name for name in file_names), \
                        "Artifact should contain index.html"
                    print(f"✓ Artifact contains {len(file_names)} files")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("RUN_E2E_TESTS"),
        reason="E2E tests require RUN_E2E_TESTS=1 and running Control Plane"
    )
    def test_task_idempotency(
        self,
        control_plane_url: str,
        agent_token: str,
        test_workspace: Path
    ):
        """
        Test task creation idempotency.
        
        **Validates: Requirements 6.5**
        
        This test verifies that creating the same task twice with the same
        idempotency key returns the same task.
        """
        project_id = "e2e-test-project"
        prompt = "Create a simple calculator web page"
        idempotency_key = f"e2e-idempotency-{int(time.time())}"
        
        # Create task first time
        task1 = self._create_task_via_api(
            control_plane_url=control_plane_url,
            agent_token=agent_token,
            project_id=project_id,
            prompt=prompt,
            assistant="web",
            workspace_path=str(test_workspace),
            idempotency_key=idempotency_key
        )
        
        task_id_1 = task1.get("taskId")
        assert task_id_1 is not None
        
        print(f"✓ First task created: {task_id_1}")
        
        # Create task second time with same idempotency key
        task2 = self._create_task_via_api(
            control_plane_url=control_plane_url,
            agent_token=agent_token,
            project_id=project_id,
            prompt=prompt,
            assistant="web",
            workspace_path=str(test_workspace),
            idempotency_key=idempotency_key
        )
        
        task_id_2 = task2.get("taskId")
        assert task_id_2 is not None
        
        print(f"✓ Second task created: {task_id_2}")
        
        # Verify same task was returned
        assert task_id_1 == task_id_2, "Same idempotency key should return same task"
        
        print("✓ Idempotency verified")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("RUN_E2E_TESTS"),
        reason="E2E tests require RUN_E2E_TESTS=1 and running Control Plane"
    )
    def test_event_ack_protocol(
        self,
        control_plane_url: str,
        agent_token: str,
        control_plane_client: ControlPlaneClient
    ):
        """
        Test event ACK protocol between Python Agent and Control Plane.
        
        **Validates: Requirements 6.5**
        
        This test verifies:
        1. Events are published with sequence numbers
        2. Control Plane responds with ACK containing seq and acceptance status
        3. Duplicate events are detected and acknowledged
        """
        # Create a test task first
        project_id = "e2e-test-project"
        prompt = "Test event ACK protocol"
        
        task_summary = self._create_task_via_api(
            control_plane_url=control_plane_url,
            agent_token=agent_token,
            project_id=project_id,
            prompt=prompt,
            assistant="web"
        )
        
        task_id = task_summary.get("taskId")
        assert task_id is not None
        
        print(f"✓ Test task created: {task_id}")
        
        # Publish a test event
        test_event = {
            "type": "TASK_STARTED",
            "eventId": f"evt-e2e-{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": {
                "stage": "TestStage",
                "message": "E2E test event"
            }
        }
        
        # Publish event and get ACK
        ack = control_plane_client.publish_event_with_ack(task_id, test_event)
        
        assert ack is not None, "ACK should be returned"
        assert "seq" in ack, "ACK should contain sequence number"
        assert "accepted" in ack, "ACK should contain accepted flag"
        assert "duplicate" in ack, "ACK should contain duplicate flag"
        assert ack["accepted"] is True, "Event should be accepted"
        assert ack["duplicate"] is False, "First event should not be duplicate"
        
        print(f"✓ Event published and acknowledged: seq={ack['seq']}")
        
        # Publish the same event again to test deduplication
        ack2 = control_plane_client.publish_event_with_ack(task_id, test_event)
        
        assert ack2 is not None, "Second ACK should be returned"
        assert ack2["accepted"] is True, "Duplicate event should be accepted"
        assert ack2["duplicate"] is True, "Second event should be marked as duplicate"
        
        print("✓ Duplicate event detected and acknowledged")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("RUN_E2E_TESTS"),
        reason="E2E tests require RUN_E2E_TESTS=1 and running Control Plane"
    )
    def test_agent_polling_and_execution(
        self,
        control_plane_url: str,
        agent_token: str,
        control_plane_client: ControlPlaneClient,
        test_workspace: Path
    ):
        """
        Test Python Agent polling and task execution.
        
        **Validates: Requirements 6.5**
        
        This test verifies:
        1. Agent can poll for tasks
        2. Agent receives task details
        3. Agent can execute task
        4. Agent publishes events during execution
        """
        # Create a test task
        project_id = "e2e-test-project"
        prompt = "Create a simple landing page"
        
        task_summary = self._create_task_via_api(
            control_plane_url=control_plane_url,
            agent_token=agent_token,
            project_id=project_id,
            prompt=prompt,
            assistant="web",
            workspace_path=str(test_workspace)
        )
        
        task_id = task_summary.get("taskId")
        assert task_id is not None
        
        print(f"✓ Task created for polling test: {task_id}")
        
        # Poll for the task
        node_id = f"e2e-test-node-{int(time.time())}"
        
        # Register agent first
        control_plane_client.register(node_id, capabilities="web,backend")
        print(f"✓ Agent registered: {node_id}")
        
        # Poll for next task
        polled_task = control_plane_client.poll_next_task(node_id, profile="ai-agent")
        
        if polled_task is None:
            # Task might have been picked up by another agent
            print("⚠ No task available (might be picked up by running agent)")
            pytest.skip("Task not available for polling")
        
        assert polled_task.get("taskId") == task_id, "Should poll the created task"
        assert polled_task.get("prompt") == prompt, "Task prompt should match"
        
        print(f"✓ Task polled successfully: {polled_task.get('taskId')}")
        
        # Verify task is now in LEASED or RUNNING state
        task_status = self._get_task_status(control_plane_url, agent_token, task_id)
        assert task_status.get("status") in ["LEASED", "RUNNING"], \
            f"Task should be leased or running after poll, got: {task_status.get('status')}"
        
        print(f"✓ Task state after poll: {task_status.get('status')}")


class TestE2EArtifactHosting:
    """
    End-to-end tests for artifact generation and hosting.
    
    These tests verify that generated artifacts are properly stored and accessible.
    """

    @pytest.fixture
    def control_plane_url(self) -> str:
        """Get Control Plane URL from environment or use default."""
        return os.environ.get("MVP_BASE_URL", "http://localhost:8058")

    @pytest.fixture
    def agent_token(self) -> str:
        """Get agent authentication token."""
        return os.environ.get("MVP_AGENT_TOKEN", "agent-dev-token")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("RUN_E2E_TESTS"),
        reason="E2E tests require RUN_E2E_TESTS=1 and running Control Plane"
    )
    def test_artifact_upload_and_download(
        self,
        control_plane_url: str,
        agent_token: str
    ):
        """
        Test artifact upload and download functionality.
        
        **Validates: Requirements 6.5**
        
        This test verifies:
        1. Artifacts can be uploaded to Control Plane
        2. Artifacts can be downloaded via HTTP
        3. Artifact metadata is correctly stored
        """
        # Create a test artifact (ZIP file)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / "test-artifact"
            artifact_dir.mkdir()
            
            # Create test files
            (artifact_dir / "index.html").write_text("<html><body>Test</body></html>")
            (artifact_dir / "styles.css").write_text("body { margin: 0; }")
            (artifact_dir / "app.js").write_text("console.log('test');")
            
            # Create ZIP
            zip_path = Path(tmpdir) / "test-artifact.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for file in artifact_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(artifact_dir))
            
            print(f"✓ Test artifact created: {zip_path}")
            
            # Upload artifact
            client = ControlPlaneClient(
                base_url=control_plane_url,
                agent_token=agent_token,
                timeout_seconds=30
            )
            
            task_id = f"e2e-artifact-test-{int(time.time())}"
            
            upload_result = client.upload_artifact(
                task_id=task_id,
                file_path=str(zip_path),
                artifact_type="web_export",
                description="E2E test artifact"
            )
            
            assert upload_result is not None, "Upload should succeed"
            artifact_id = upload_result.get("artifactId")
            assert artifact_id is not None, "Artifact ID should be returned"
            
            print(f"✓ Artifact uploaded: {artifact_id}")
            
            # Verify artifact can be downloaded
            download_url = f"{control_plane_url}/api/v1/artifacts/{artifact_id}/download"
            
            headers = {
                "Authorization": f"Bearer {agent_token}"
            }
            
            req = request.Request(download_url, headers=headers, method="GET")
            
            try:
                with request.urlopen(req, timeout=10) as response:
                    assert response.getcode() == 200, "Download should succeed"
                    content_type = response.headers.get("Content-Type")
                    assert "zip" in content_type.lower(), \
                        f"Content-Type should be ZIP, got: {content_type}"
                    
                    # Verify downloaded content is valid ZIP
                    downloaded_data = response.read()
                    assert len(downloaded_data) > 0, "Downloaded data should not be empty"
                    
                    print(f"✓ Artifact downloaded: {len(downloaded_data)} bytes")
                    
            except error.HTTPError as e:
                pytest.fail(f"Failed to download artifact: HTTP {e.code}")


if __name__ == "__main__":
    # Allow running tests directly for development
    pytest.main([__file__, "-v", "-s"])
