"""
Unit and property-based tests for BaseWorkflow and WorkflowState.

Task 21.1: Create LangGraph workflow base classes

Tests cover:
- WorkflowState initialization and field validation
- Error handling and retry logic
- LangChain adapter (LLMClient) integration
- Property tests for workflow state transitions

**Validates: Requirements 8.5**
"""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st
from langgraph.graph import StateGraph, END

from workflows.base_workflow import (
    MAX_RETRY_COUNT,
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
    WORKFLOW_STAGE_RETRYING,
    WORKFLOW_STAGE_RUNNING,
    BaseWorkflow,
    WorkflowState,
    _build_error_record,
    _is_retryable_error,
)
from utils.errors import (
    AgentError,
    LLMError,
    PluginError,
    ProtocolError,
    SandboxError,
    ValidationError,
)
from config.timeout_config import DEFAULT_TIMEOUT_CONFIG, TimeoutConfig, StageTimeoutConfig


# ---------------------------------------------------------------------------
# Concrete workflow implementation for testing
# ---------------------------------------------------------------------------

class _EchoWorkflow(BaseWorkflow):
    """Minimal concrete workflow that echoes the task back in state."""

    def build_graph(self) -> StateGraph:
        graph = StateGraph(WorkflowState)

        def echo_node(state: WorkflowState) -> WorkflowState:
            updated = dict(state)
            updated["stage"] = WORKFLOW_STAGE_COMPLETED
            updated["metadata"] = {**(state.get("metadata") or {}), "echoed": True}
            return updated

        graph.add_node("echo", echo_node)
        graph.set_entry_point("echo")
        graph.add_edge("echo", END)
        return graph

    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        return WorkflowState(
            task_id=str(task.get("task_id", "")),
            intent=str(task.get("intent", "")),
            plan={},
            code={},
            errors=[],
            metadata={},
            stage=WORKFLOW_STAGE_INIT,
            retry_count=0,
        )


class _FailingWorkflow(BaseWorkflow):
    """Workflow whose graph node always raises an exception."""

    def __init__(self, error: Exception, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._error = error

    def build_graph(self) -> StateGraph:
        error = self._error

        graph = StateGraph(WorkflowState)

        def fail_node(state: WorkflowState) -> WorkflowState:
            raise error

        graph.add_node("fail", fail_node)
        graph.set_entry_point("fail")
        graph.add_edge("fail", END)
        return graph

    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        return WorkflowState(
            task_id=str(task.get("task_id", "")),
            intent="",
            plan={},
            code={},
            errors=[],
            metadata={},
            stage=WORKFLOW_STAGE_RUNNING,
            retry_count=0,
        )


# ---------------------------------------------------------------------------
# WorkflowState initialization tests
# ---------------------------------------------------------------------------

class TestWorkflowStateInitialization:
    """Tests for WorkflowState TypedDict initialization."""

    def test_workflow_state_can_be_created_with_all_fields(self):
        state: WorkflowState = {
            "task_id": "task-123",
            "intent": "backend_generation",
            "plan": {"steps": ["model", "routes"]},
            "code": {"app.py": "# Flask app"},
            "errors": [],
            "metadata": {"trace_id": "abc"},
            "stage": WORKFLOW_STAGE_INIT,
            "retry_count": 0,
        }
        assert state["task_id"] == "task-123"
        assert state["intent"] == "backend_generation"
        assert state["stage"] == WORKFLOW_STAGE_INIT
        assert state["retry_count"] == 0

    def test_workflow_state_can_be_created_with_partial_fields(self):
        """WorkflowState is total=False so partial creation is valid."""
        state: WorkflowState = {"task_id": "task-456"}
        assert state["task_id"] == "task-456"

    def test_workflow_state_errors_field_is_list(self):
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [],
            "stage": WORKFLOW_STAGE_INIT,
            "retry_count": 0,
        }
        assert isinstance(state["errors"], list)

    def test_workflow_state_metadata_field_is_dict(self):
        state: WorkflowState = {
            "task_id": "t1",
            "metadata": {"key": "value"},
            "stage": WORKFLOW_STAGE_INIT,
            "retry_count": 0,
        }
        assert isinstance(state["metadata"], dict)
        assert state["metadata"]["key"] == "value"

    def test_workflow_state_code_field_is_dict(self):
        state: WorkflowState = {
            "task_id": "t1",
            "code": {"app.py": "print('hello')"},
            "stage": WORKFLOW_STAGE_INIT,
            "retry_count": 0,
        }
        assert state["code"]["app.py"] == "print('hello')"

    def test_workflow_state_plan_field_is_dict(self):
        state: WorkflowState = {
            "task_id": "t1",
            "plan": {"steps": ["a", "b"]},
            "stage": WORKFLOW_STAGE_INIT,
            "retry_count": 0,
        }
        assert state["plan"]["steps"] == ["a", "b"]

    def test_workflow_stage_constants_are_distinct(self):
        stages = {
            WORKFLOW_STAGE_INIT,
            WORKFLOW_STAGE_RUNNING,
            WORKFLOW_STAGE_COMPLETED,
            WORKFLOW_STAGE_FAILED,
            WORKFLOW_STAGE_RETRYING,
        }
        assert len(stages) == 5


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestWorkflowErrorHandling:
    """Tests for _handle_error and _build_error_record."""

    def test_build_error_record_from_agent_error(self):
        error = LLMError("LLM timed out", error_code="LLM_TIMEOUT")
        record = _build_error_record(error, stage="intent", task_id="t1")

        assert record["errorType"] == "LLMError"
        assert record["stage"] == "intent"
        assert record["taskId"] == "t1"
        assert "timestamp" in record
        assert isinstance(record["timestamp"], float)

    def test_build_error_record_from_generic_exception(self):
        error = RuntimeError("unexpected failure")
        record = _build_error_record(error, stage="coder", task_id="t2")

        assert record["errorType"] == "RuntimeError"
        assert record["stage"] == "coder"
        assert record["taskId"] == "t2"
        assert record["retryable"] is False

    def test_build_error_record_timestamp_is_recent(self):
        before = time.time()
        record = _build_error_record(ValueError("x"), stage="test")
        after = time.time()

        assert before <= record["timestamp"] <= after

    def test_handle_error_appends_to_errors_list(self):
        workflow = _EchoWorkflow()
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        error = ValidationError("syntax error")
        updated = workflow._handle_error(state, error, stage="coder")

        assert len(updated["errors"]) == 1
        assert updated["errors"][0]["errorType"] == "ValidationError"

    def test_handle_error_preserves_existing_errors(self):
        workflow = _EchoWorkflow()
        existing_error = {"errorType": "LLMError", "stage": "intent"}
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [existing_error],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        error = SandboxError("sandbox crashed", error_code="SANDBOX_UNAVAILABLE")
        updated = workflow._handle_error(state, error, stage="coder")

        assert len(updated["errors"]) == 2
        assert updated["errors"][0] == existing_error

    def test_handle_error_sets_failed_stage_for_non_retryable(self):
        workflow = _EchoWorkflow()
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        error = ValidationError("bad syntax")  # non-retryable
        updated = workflow._handle_error(state, error, stage="coder")

        assert updated["stage"] == WORKFLOW_STAGE_FAILED

    def test_handle_error_sets_retrying_stage_for_retryable_within_limit(self):
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        error = LLMError("timeout", error_code="LLM_TIMEOUT")  # retryable
        updated = workflow._handle_error(state, error, stage="intent")

        assert updated["stage"] == WORKFLOW_STAGE_RETRYING

    def test_handle_error_sets_failed_stage_when_retries_exhausted(self):
        workflow = _EchoWorkflow(max_retries=2)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 2,  # already at max
        }
        error = LLMError("timeout", error_code="LLM_TIMEOUT")
        updated = workflow._handle_error(state, error, stage="intent")

        assert updated["stage"] == WORKFLOW_STAGE_FAILED

    def test_handle_error_does_not_mutate_original_state(self):
        workflow = _EchoWorkflow()
        original_errors: list = []
        state: WorkflowState = {
            "task_id": "t1",
            "errors": original_errors,
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        workflow._handle_error(state, ValueError("x"), stage="test")

        # Original list must not be mutated
        assert original_errors == []


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------

class TestWorkflowRetryLogic:
    """Tests for _should_retry."""

    def test_should_retry_returns_true_for_retryable_error_within_limit(self):
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [{"retryable": True}],
            "stage": WORKFLOW_STAGE_RETRYING,
            "retry_count": 1,
        }
        assert workflow._should_retry(state) is True

    def test_should_retry_returns_false_when_stage_is_not_retrying(self):
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [{"retryable": True}],
            "stage": WORKFLOW_STAGE_FAILED,
            "retry_count": 0,
        }
        assert workflow._should_retry(state) is False

    def test_should_retry_returns_false_when_retry_count_at_max(self):
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [{"retryable": True}],
            "stage": WORKFLOW_STAGE_RETRYING,
            "retry_count": 3,
        }
        assert workflow._should_retry(state) is False

    def test_should_retry_returns_false_when_last_error_not_retryable(self):
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [{"retryable": False}],
            "stage": WORKFLOW_STAGE_RETRYING,
            "retry_count": 0,
        }
        assert workflow._should_retry(state) is False

    def test_should_retry_returns_false_when_no_errors(self):
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [],
            "stage": WORKFLOW_STAGE_RETRYING,
            "retry_count": 0,
        }
        assert workflow._should_retry(state) is False

    def test_max_retries_zero_disables_retry(self):
        workflow = _EchoWorkflow(max_retries=0)
        state: WorkflowState = {
            "task_id": "t1",
            "errors": [{"retryable": True}],
            "stage": WORKFLOW_STAGE_RETRYING,
            "retry_count": 0,
        }
        assert workflow._should_retry(state) is False


# ---------------------------------------------------------------------------
# is_retryable_error tests
# ---------------------------------------------------------------------------

class TestIsRetryableError:
    """Tests for the _is_retryable_error helper."""

    def test_llm_timeout_is_retryable(self):
        assert _is_retryable_error(LLMError("timeout", error_code="LLM_TIMEOUT")) is True

    def test_llm_rate_limit_is_retryable(self):
        assert _is_retryable_error(LLMError("rate limit", error_code="LLM_RATE_LIMIT")) is True

    def test_sandbox_unavailable_is_retryable(self):
        assert _is_retryable_error(SandboxError("down", error_code="SANDBOX_UNAVAILABLE")) is True

    def test_validation_error_is_not_retryable(self):
        assert _is_retryable_error(ValidationError("syntax")) is False

    def test_plugin_error_is_not_retryable(self):
        assert _is_retryable_error(PluginError("not found", error_code="PLUGIN_NOT_FOUND")) is False

    def test_generic_exception_is_not_retryable(self):
        assert _is_retryable_error(RuntimeError("unexpected")) is False

    def test_protocol_ack_timeout_is_retryable(self):
        assert _is_retryable_error(ProtocolError("ack timeout", error_code="PROTOCOL_ACK_TIMEOUT")) is True


# ---------------------------------------------------------------------------
# LangChain adapter integration tests
# ---------------------------------------------------------------------------

class TestLangChainAdapterIntegration:
    """
    Tests verifying integration with existing LangChain model adapters.

    **Validates: Requirements 8.5**
    """

    def test_llm_client_property_creates_default_client_when_none(self):
        """BaseWorkflow.llm_client SHALL create a default LLMClient on first access."""
        workflow = _EchoWorkflow(llm_client=None)
        from llm.llm_client import LLMClient
        client = workflow.llm_client
        assert isinstance(client, LLMClient)

    def test_llm_client_property_returns_provided_client(self):
        """BaseWorkflow.llm_client SHALL return the injected client."""
        mock_client = MagicMock()
        workflow = _EchoWorkflow(llm_client=mock_client)
        assert workflow.llm_client is mock_client

    def test_llm_client_is_cached_after_first_access(self):
        """BaseWorkflow.llm_client SHALL return the same instance on repeated access."""
        workflow = _EchoWorkflow(llm_client=None)
        client1 = workflow.llm_client
        client2 = workflow.llm_client
        assert client1 is client2

    def test_workflow_accepts_custom_timeout_config(self):
        """BaseWorkflow SHALL accept a custom TimeoutConfig."""
        custom_config = TimeoutConfig(
            intent=StageTimeoutConfig(stage="intent", timeout_seconds=10),
            planner=StageTimeoutConfig(stage="planner", timeout_seconds=20),
            coder=StageTimeoutConfig(stage="coder", timeout_seconds=30),
            reviewer=StageTimeoutConfig(stage="reviewer", timeout_seconds=40),
            tester=StageTimeoutConfig(stage="tester", timeout_seconds=50),
            max_task_execution_seconds=120,
        )
        workflow = _EchoWorkflow(timeout_config=custom_config)
        assert workflow._timeout_config is custom_config

    def test_workflow_uses_default_timeout_config_when_none(self):
        """BaseWorkflow SHALL use DEFAULT_TIMEOUT_CONFIG when none is provided."""
        workflow = _EchoWorkflow()
        assert workflow._timeout_config is DEFAULT_TIMEOUT_CONFIG

    def test_workflow_run_uses_llm_client_for_generation(self):
        """
        Workflow nodes can access the LLMClient via self.llm_client.

        **Validates: Requirements 8.5**
        """
        mock_client = MagicMock()
        mock_client.generate.return_value = "generated code"

        class _LLMWorkflow(BaseWorkflow):
            def build_graph(self) -> StateGraph:
                workflow_self = self
                graph = StateGraph(WorkflowState)

                def llm_node(state: WorkflowState) -> WorkflowState:
                    result = workflow_self.llm_client.generate("prompt")
                    updated = dict(state)
                    updated["code"] = {"result": result}
                    updated["stage"] = WORKFLOW_STAGE_COMPLETED
                    return updated

                graph.add_node("llm", llm_node)
                graph.set_entry_point("llm")
                graph.add_edge("llm", END)
                return graph

            def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
                return WorkflowState(
                    task_id=str(task.get("task_id", "")),
                    intent="",
                    plan={},
                    code={},
                    errors=[],
                    metadata={},
                    stage=WORKFLOW_STAGE_INIT,
                    retry_count=0,
                )

        workflow = _LLMWorkflow(llm_client=mock_client)
        result = workflow.run({"task_id": "t1"})

        mock_client.generate.assert_called_once_with("prompt")
        assert result["code"]["result"] == "generated code"


# ---------------------------------------------------------------------------
# BaseWorkflow.run integration tests
# ---------------------------------------------------------------------------

class TestBaseWorkflowRun:
    """Integration tests for BaseWorkflow.run."""

    def test_run_returns_final_state_on_success(self):
        workflow = _EchoWorkflow()
        result = workflow.run({"task_id": "task-001", "intent": "analyze"})

        assert result["task_id"] == "task-001"
        assert result["stage"] == WORKFLOW_STAGE_COMPLETED
        assert result["metadata"]["echoed"] is True

    def test_run_returns_failed_state_on_non_retryable_error(self):
        error = ValidationError("syntax error")
        workflow = _FailingWorkflow(error=error, max_retries=3)
        result = workflow.run({"task_id": "task-002"})

        assert result["stage"] == WORKFLOW_STAGE_FAILED
        assert len(result["errors"]) >= 1

    def test_run_caches_compiled_graph(self):
        """run() SHALL compile the graph only once."""
        workflow = _EchoWorkflow()
        workflow.run({"task_id": "t1"})
        graph_after_first = workflow._graph

        workflow.run({"task_id": "t2"})
        graph_after_second = workflow._graph

        assert graph_after_first is graph_after_second

    def test_run_propagates_task_id_to_state(self):
        workflow = _EchoWorkflow()
        result = workflow.run({"task_id": "my-task-id"})
        assert result["task_id"] == "my-task-id"

    def test_run_with_retryable_error_exhausts_retries(self):
        """
        When a retryable error is raised repeatedly, run() SHALL exhaust
        retries and return a failed state.
        """
        error = LLMError("timeout", error_code="LLM_TIMEOUT")
        workflow = _FailingWorkflow(error=error, max_retries=2)
        result = workflow.run({"task_id": "task-retry"})

        assert result["stage"] == WORKFLOW_STAGE_FAILED
        # Should have accumulated errors from each attempt
        assert len(result["errors"]) >= 1


# ---------------------------------------------------------------------------
# Property-based tests for workflow state transitions
# ---------------------------------------------------------------------------

# Strategies
_task_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=64,
)
_intent_strategy = st.sampled_from([
    "backend_generation", "analyze", "test", "code_change", "deploy", "fullstack",
])
_retry_count_strategy = st.integers(min_value=0, max_value=10)
_max_retries_strategy = st.integers(min_value=0, max_value=5)


class TestProperty28WorkflowStateTransitions:
    """
    **Property 28: LangGraph Integration Compatibility**

    For any LangGraph operation, the engine SHALL integrate with existing
    LangChain model and tool adapters.

    **Validates: Requirements 8.5**
    """

    @given(_task_id_strategy, _intent_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_28_initial_state_preserves_task_id_and_intent(
        self, task_id: str, intent: str
    ):
        """
        **Property 28  For any task_id and intent, get_initial_state SHALL
        preserve both values in the returned WorkflowState.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow()
        state = workflow.get_initial_state({"task_id": task_id, "intent": intent})

        assert state["task_id"] == task_id
        assert state["intent"] == intent

    @given(_task_id_strategy, _intent_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_28_initial_state_has_zero_retry_count(
        self, task_id: str, intent: str
    ):
        """
        **Property 28  For any task, the initial retry_count SHALL be 0.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow()
        state = workflow.get_initial_state({"task_id": task_id, "intent": intent})

        assert state["retry_count"] == 0

    @given(_task_id_strategy, _intent_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_28_initial_state_has_empty_errors(
        self, task_id: str, intent: str
    ):
        """
        **Property 28  For any task, the initial errors list SHALL be empty.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow()
        state = workflow.get_initial_state({"task_id": task_id, "intent": intent})

        assert state["errors"] == []

    @given(_task_id_strategy, _intent_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_28_successful_run_produces_completed_stage(
        self, task_id: str, intent: str
    ):
        """
        **Property 28  For any task that completes without error, the final
        stage SHALL be WORKFLOW_STAGE_COMPLETED.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow()
        result = workflow.run({"task_id": task_id, "intent": intent})

        assert result["stage"] == WORKFLOW_STAGE_COMPLETED

    @given(_retry_count_strategy, _max_retries_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_28_should_retry_is_consistent_with_retry_count(
        self, retry_count: int, max_retries: int
    ):
        """
        **Property 28  _should_retry SHALL return False when retry_count >= max_retries.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow(max_retries=max_retries)
        state: WorkflowState = {
            "task_id": "t",
            "errors": [{"retryable": True}],
            "stage": WORKFLOW_STAGE_RETRYING,
            "retry_count": retry_count,
        }

        result = workflow._should_retry(state)

        if retry_count >= max_retries:
            assert result is False
        # When retry_count < max_retries and error is retryable, result may be True

    @given(_task_id_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_28_handle_error_always_appends_error_record(
        self, task_id: str
    ):
        """
        **Property 28  _handle_error SHALL always append exactly one error
        record to the errors list.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow()
        initial_errors: list = []
        state: WorkflowState = {
            "task_id": task_id,
            "errors": initial_errors,
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        error = RuntimeError("test error")
        updated = workflow._handle_error(state, error, stage="test")

        assert len(updated["errors"]) == len(initial_errors) + 1

    @given(_task_id_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_28_handle_error_does_not_mutate_input_state(
        self, task_id: str
    ):
        """
        **Property 28  _handle_error SHALL NOT mutate the input state.**

        **Validates: Requirements 8.5**
        """
        workflow = _EchoWorkflow()
        original_errors: list = []
        state: WorkflowState = {
            "task_id": task_id,
            "errors": original_errors,
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        workflow._handle_error(state, ValueError("x"), stage="test")

        # Original list must not be mutated
        assert original_errors == []


class TestProperty29WorkflowErrorHandling:
    """
    **Property 29: LangGraph Error Handling**

    For any LangGraph operation failure, the system SHALL provide clear
    error categorization and fallback options.

    **Validates: Requirements 8.6**
    """

    @given(
        st.sampled_from([
            LLMError("timeout", error_code="LLM_TIMEOUT"),
            LLMError("rate limit", error_code="LLM_RATE_LIMIT"),
            SandboxError("unavailable", error_code="SANDBOX_UNAVAILABLE"),
            ProtocolError("ack timeout", error_code="PROTOCOL_ACK_TIMEOUT"),
        ])
    )
    @settings(max_examples=20, deadline=None)
    def test_property_29_retryable_errors_set_retrying_stage(
        self, error: AgentError
    ):
        """
        **Property 29  For any retryable error within retry limit, _handle_error
        SHALL set stage to WORKFLOW_STAGE_RETRYING.**

        **Validates: Requirements 8.6**
        """
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t",
            "errors": [],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        updated = workflow._handle_error(state, error, stage="intent")

        assert updated["stage"] == WORKFLOW_STAGE_RETRYING

    @given(
        st.sampled_from([
            ValidationError("syntax"),
            PluginError("not found", error_code="PLUGIN_NOT_FOUND"),
        ])
    )
    @settings(max_examples=20, deadline=None)
    def test_property_29_non_retryable_errors_set_failed_stage(
        self, error: AgentError
    ):
        """
        **Property 29  For any non-retryable error, _handle_error SHALL set
        stage to WORKFLOW_STAGE_FAILED.**

        **Validates: Requirements 8.6**
        """
        workflow = _EchoWorkflow(max_retries=3)
        state: WorkflowState = {
            "task_id": "t",
            "errors": [],
            "stage": WORKFLOW_STAGE_RUNNING,
            "retry_count": 0,
        }
        updated = workflow._handle_error(state, error, stage="coder")

        assert updated["stage"] == WORKFLOW_STAGE_FAILED

    @given(_task_id_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_29_error_record_always_has_required_fields(
        self, task_id: str
    ):
        """
        **Property 29  For any error, _build_error_record SHALL produce a
        record with errorType, stage, taskId, and timestamp fields.**

        **Validates: Requirements 8.6**
        """
        error = RuntimeError("test")
        record = _build_error_record(error, stage="test_stage", task_id=task_id)

        assert "errorType" in record
        assert "stage" in record
        assert "taskId" in record
        assert "timestamp" in record
        assert record["taskId"] == task_id
        assert record["stage"] == "test_stage"
