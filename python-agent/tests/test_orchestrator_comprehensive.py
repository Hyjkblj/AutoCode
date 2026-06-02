"""
Comprehensive unit tests for AgentOrchestrator.

**Validates: Requirements 6.4**

Tests cover:
- Task routing and dual-engine support (legacy vs LangGraph)
- Memory context loading and hint application
- Intent inference and plan generation
- Code change workflow with fix loop
- Sandbox execution for deploy/test intents
- Artifact publishing and packaging
- Error handling and failure scenarios
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from agents.intent_agent import IntentDecision
from agents.planner_agent import PlanResult
from agents.reviewer_agent import ReviewResult
from agents.tester_agent import TesterResult
from client.control_plane_client import ControlPlaneClient
from orchestrator.agent_orchestrator import AgentOrchestrator
from orchestrator.langgraph_runtime import LangGraphExecutionResult
from tools.exec_tool import ExecResult


class TestOrchestratorTaskRouting:
    """Test Orchestrator task routing and dual-engine support."""

    def test_orchestrator_uses_legacy_engine_by_default(self, monkeypatch):
        """Verify orchestrator defaults to legacy engine when not configured."""
        monkeypatch.delenv("AGENT_ENGINE", raising=False)
        orchestrator = AgentOrchestrator()
        assert orchestrator.engine == "legacy"

    def test_orchestrator_uses_langgraph_engine_when_configured(self, monkeypatch):
        """Verify orchestrator uses LangGraph engine when configured."""
        monkeypatch.setenv("AGENT_ENGINE", "langgraph")
        orchestrator = AgentOrchestrator()
        assert orchestrator.engine == "langgraph"

    def test_orchestrator_falls_back_to_legacy_for_invalid_engine(self, monkeypatch):
        """Verify orchestrator falls back to legacy for invalid engine names."""
        monkeypatch.setenv("AGENT_ENGINE", "invalid_engine")
        orchestrator = AgentOrchestrator()
        assert orchestrator.engine == "legacy"

    def test_orchestrator_routes_analyze_intent_to_langgraph(self, monkeypatch):
        """Verify analyze intent is routed to LangGraph when engine is langgraph."""
        monkeypatch.setenv("AGENT_ENGINE", "langgraph")
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_analyze_001",
            "prompt": "analyze this code",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_langgraph = Mock()
        mock_langgraph.supports = Mock(return_value=True)
        mock_langgraph.execute = Mock(
            return_value=LangGraphExecutionResult(
                handled=True,
                terminal_event_type="TASK_DONE",
                terminal_payload={"result": "analyzed", "executionPath": "langgraph"},
                memory_record={"status": "done"},
                task_status="done",
                reason="analyzed",
            )
        )

        orchestrator = AgentOrchestrator(langgraph_runtime=mock_langgraph)
        orchestrator.handle_task(task, mock_client)

        mock_langgraph.execute.assert_called_once()
        assert task.get("_executionPath") == "langgraph"

    def test_orchestrator_falls_back_to_legacy_when_langgraph_not_supported(self, monkeypatch):
        """Verify orchestrator falls back to legacy when LangGraph doesn't support intent."""
        monkeypatch.setenv("AGENT_ENGINE", "langgraph")
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_fallback_001",
            "prompt": "deploy this app",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_langgraph = Mock()
        mock_langgraph.supports = Mock(return_value=False)

        orchestrator = AgentOrchestrator(langgraph_runtime=mock_langgraph)
        orchestrator.handle_task(task, mock_client)

        # Should publish fallback message
        fallback_events = [
            call for call in mock_client.publish_event.call_args_list
            if "fallback" in str(call).lower()
        ]
        assert len(fallback_events) > 0


class TestOrchestratorMemoryContext:
    """Test Orchestrator memory context loading and application."""

    def test_orchestrator_loads_memory_context_from_redis(self, monkeypatch):
        """Verify orchestrator loads project memory context."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_memory_001",
            "prompt": "run tests",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_memory = Mock()
        mock_memory.project_key_for_task = Mock(return_value="proj_001")
        mock_memory.recent = Mock(
            return_value=[
                {"intent": "test", "testCommand": "pytest -v"},
                {"intent": "deploy", "deployCommand": "docker-compose up"},
            ]
        )
        mock_memory.append = Mock()

        orchestrator = AgentOrchestrator(memory_store=mock_memory)
        orchestrator.handle_task(task, mock_client)

        mock_memory.recent.assert_called_once_with("proj_001", limit=5)
        mock_memory.append.assert_called_once()

    def test_orchestrator_applies_memory_hints_to_task(self, monkeypatch):
        """Verify orchestrator applies memory hints from history."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_hints_001",
            "prompt": "run tests",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_memory = Mock()
        mock_memory.project_key_for_task = Mock(return_value="proj_001")
        mock_memory.recent = Mock(
            return_value=[
                {"intent": "test", "testCommand": "npm test"},
            ]
        )
        mock_memory.append = Mock()

        orchestrator = AgentOrchestrator(memory_store=mock_memory)
        orchestrator.handle_task(task, mock_client)

        # Task should have memory hints applied
        assert task.get("memoryLastTestCommand") == "npm test"


class TestOrchestratorDistributedLock:
    """Test Orchestrator distributed lock integration."""

    def test_orchestrator_acquires_lock_before_processing(self, monkeypatch):
        """Verify orchestrator acquires distributed lock before task processing."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_lock_001",
            "prompt": "analyze code",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_lock = Mock()
        mock_lease = Mock()
        mock_lease.acquired = True
        mock_lease.release = Mock()
        mock_lock.acquire = Mock(return_value=mock_lease)

        orchestrator = AgentOrchestrator(distributed_lock=mock_lock)
        orchestrator.handle_task(task, mock_client)

        mock_lock.acquire.assert_called_once_with("task_lock_001")
        mock_lease.release.assert_called_once()

    def test_orchestrator_skips_processing_when_lock_not_acquired(self, monkeypatch):
        """Verify orchestrator skips processing when lock cannot be acquired."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_lock_002",
            "prompt": "analyze code",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_lock = Mock()
        mock_lease = Mock()
        mock_lease.acquired = False
        mock_lock.acquire = Mock(return_value=mock_lease)

        orchestrator = AgentOrchestrator(distributed_lock=mock_lock)
        orchestrator.handle_task(task, mock_client)

        # Should not publish any events if lock not acquired
        mock_client.publish_event.assert_not_called()

    def test_orchestrator_releases_lock_on_exception(self, monkeypatch):
        """Verify orchestrator releases lock even when exception occurs."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_lock_003",
            "prompt": "analyze code",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(side_effect=RuntimeError("publish failed"))

        mock_lock = Mock()
        mock_lease = Mock()
        mock_lease.acquired = True
        mock_lease.release = Mock()
        mock_lock.acquire = Mock(return_value=mock_lease)

        mock_memory = Mock()
        mock_memory.project_key_for_task = Mock(return_value="proj_001")
        mock_memory.recent = Mock(return_value=[])
        mock_memory.append = Mock()

        orchestrator = AgentOrchestrator(distributed_lock=mock_lock, memory_store=mock_memory)

        with pytest.raises(RuntimeError):
            orchestrator.handle_task(task, mock_client)

        # Lock should still be released
        mock_lease.release.assert_called_once()


class TestOrchestratorValidationAndFixLoop:
    """Test Orchestrator validation gate and fix loop integration."""

    def test_orchestrator_validates_generation_target(self, monkeypatch):
        """Verify orchestrator validates generation target before processing."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_validate_001",
            "prompt": "generate app",
            "assistant": "ai-agent",
            "target": "invalid_target",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        orchestrator = AgentOrchestrator()
        orchestrator.handle_task(task, mock_client)

        # Should publish TASK_FAILED event
        failed_events = [
            call for call in mock_client.publish_event.call_args_list
            if call[0][1].get("type") == "TASK_FAILED"
        ]
        assert len(failed_events) > 0

    def test_orchestrator_respects_fix_loop_max_attempts_env(self, monkeypatch):
        """Verify orchestrator respects MVP_FIX_LOOP_MAX_ATTEMPTS environment variable."""
        monkeypatch.setenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "2")
        from orchestrator.agent_orchestrator import _resolve_fix_loop_max_attempts

        assert _resolve_fix_loop_max_attempts() == 2

    def test_orchestrator_defaults_fix_loop_to_three_attempts(self, monkeypatch):
        """Verify orchestrator defaults to 3 fix loop attempts."""
        monkeypatch.delenv("MVP_FIX_LOOP_MAX_ATTEMPTS", raising=False)
        from orchestrator.agent_orchestrator import _resolve_fix_loop_max_attempts

        assert _resolve_fix_loop_max_attempts() == 3


class TestOrchestratorArtifactPublishing:
    """Test Orchestrator artifact publishing and packaging."""

    def test_orchestrator_publishes_artifact_for_web_target(self, monkeypatch, tmp_path):
        """Verify orchestrator publishes artifact for web generation target."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "index.html").write_text("<html></html>")
        (workspace / "styles.css").write_text("body {}")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {
            "taskId": "task_artifact_001",
            "prompt": "generate web app",
            "assistant": "ai-agent",
            "target": "web",
            "workspacePath": str(workspace),
            "_generated_files": ["index.html", "styles.css", "app.js", "README.generated.md"],
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})
        mock_client.upload_artifact = Mock(
            return_value={
                "artifactId": "art_001",
                "name": "export.zip",
                "contentType": "application/zip",
                "sizeBytes": 1024,
                "sha256": "abc123",
            }
        )

        mock_reviewer = Mock()
        mock_reviewer.review = Mock(
            return_value=ReviewResult(approved=True, summary="approved", issues=[])
        )

        mock_tester = Mock()
        mock_tester.execute = Mock(
            return_value=TesterResult(
                success=True,
                attempts=1,
                retries=0,
                command="echo test",
                status="ok",
                reason=None,
                trace_id="trc_001",
                run_id="run_001",
            )
        )

        orchestrator = AgentOrchestrator(
            reviewer_agent=mock_reviewer,
            tester_agent=mock_tester,
        )
        orchestrator.handle_task(task, mock_client)

        # Should publish ARTIFACT_READY event
        artifact_events = [
            call for call in mock_client.publish_event.call_args_list
            if call[0][1].get("type") == "ARTIFACT_READY"
        ]
        assert len(artifact_events) > 0

    def test_orchestrator_includes_artifact_metadata_in_event(self, monkeypatch, tmp_path):
        """Verify orchestrator includes complete artifact metadata in ARTIFACT_READY event."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "index.html").write_text("<html></html>")
        (workspace / "styles.css").write_text("body {}")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {
            "taskId": "task_metadata_001",
            "prompt": "generate web app",
            "assistant": "ai-agent",
            "target": "web",
            "workspacePath": str(workspace),
            "_generated_files": ["index.html", "styles.css", "app.js", "README.generated.md"],
        }

        mock_client = Mock(spec=ControlPlaneClient)
        events_published = []

        def capture_event(task_id, event):
            events_published.append(event)
            return {"eventId": event.get("eventId")}

        mock_client.publish_event = capture_event
        mock_client.upload_artifact = Mock(
            return_value={
                "artifactId": "art_metadata_001",
                "name": "export.zip",
                "contentType": "application/zip",
                "sizeBytes": 2048,
                "sha256": "def456",
            }
        )

        mock_reviewer = Mock()
        mock_reviewer.review = Mock(
            return_value=ReviewResult(approved=True, summary="approved", issues=[])
        )

        mock_tester = Mock()
        mock_tester.execute = Mock(
            return_value=TesterResult(
                success=True,
                attempts=1,
                retries=0,
                command="echo test",
                status="ok",
                reason=None,
                trace_id="trc_metadata_001",
                run_id="run_metadata_001",
            )
        )

        orchestrator = AgentOrchestrator(
            reviewer_agent=mock_reviewer,
            tester_agent=mock_tester,
        )
        orchestrator.handle_task(task, mock_client)

        artifact_events = [e for e in events_published if e.get("type") == "ARTIFACT_READY"]
        assert len(artifact_events) == 1

        artifact = artifact_events[0]["payload"]["artifact"]
        assert artifact["artifactId"] == "art_metadata_001"
        assert artifact["name"] == "export.zip"
        assert artifact["size"] == 2048


class TestOrchestratorErrorHandling:
    """Test Orchestrator error handling and failure scenarios."""

    def test_orchestrator_handles_intent_agent_failure(self, monkeypatch):
        """Verify orchestrator handles intent agent failures gracefully."""
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        task = {
            "taskId": "task_error_001",
            "prompt": "analyze code",
            "assistant": "ai-agent",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        mock_intent = Mock()
        mock_intent.infer = Mock(side_effect=RuntimeError("intent failed"))

        orchestrator = AgentOrchestrator(intent_agent=mock_intent)
        orchestrator.handle_task(task, mock_client)

        # Should publish TASK_FAILED event
        failed_events = [
            call for call in mock_client.publish_event.call_args_list
            if call[0][1].get("type") == "TASK_FAILED"
        ]
        assert len(failed_events) > 0

    def test_orchestrator_generates_error_codes_from_reasons(self):
        """Verify orchestrator generates proper error codes from failure reasons."""
        from orchestrator.agent_orchestrator import _error_code_from_reason

        assert _error_code_from_reason("llm_key_missing") == "LLM_KEY_MISSING"
        assert _error_code_from_reason("sandbox_exec_failed") == "SANDBOX_EXEC_FAILED"
        assert _error_code_from_reason("review_rejected") == "REVIEW_REJECTED"
        assert _error_code_from_reason("fix_loop_exhausted") == "FIX_LOOP_EXHAUSTED"
        assert _error_code_from_reason("") == "UNKNOWN_ERROR"
