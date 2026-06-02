"""
Unit and property-based tests for CodeChangeWorkflow.

Task 22.1: Implement code_change LangGraph workflow

Tests cover:
- CodeChangeWorkflow: initial state (task_id, intent, stage, retry_count, errors)
- run() output format (required keys, executionPath, success)
- Error handling (LLM failure → graceful degradation via retry/fallback)
- get_code_change_result() and get_memory_record() helper methods
- Property test: for any task_id/prompt, run() always returns a dict with
  "intent" == "code_change"

**Validates: Requirements 8.3, 8.6**
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from workflows.base_workflow import (
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
)
from workflows.code_change_workflow import CodeChangeWorkflow
from utils.errors import LLMError, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(response: str = "mock code change response") -> MagicMock:
    """Return a mock LLMClient whose generate() returns *response*."""
    mock = MagicMock()
    mock.generate.return_value = response
    return mock


def _make_failing_llm(exc: Exception | None = None) -> MagicMock:
    """Return a mock LLMClient whose generate() raises *exc*."""
    if exc is None:
        exc = RuntimeError("LLM unavailable")
    mock = MagicMock()
    mock.generate.side_effect = exc
    return mock


# ---------------------------------------------------------------------------
# Initial state tests
# ---------------------------------------------------------------------------

class TestCodeChangeWorkflowInitialState:
    """Tests for CodeChangeWorkflow.get_initial_state."""

    def test_initial_state_sets_task_id(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "task-abc"})
        assert state["task_id"] == "task-abc"

    def test_initial_state_sets_intent_to_code_change(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["intent"] == "code_change"

    def test_initial_state_stage_is_init(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["stage"] == WORKFLOW_STAGE_INIT

    def test_initial_state_retry_count_is_zero(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["retry_count"] == 0

    def test_initial_state_errors_is_empty(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["errors"] == []

    def test_initial_state_stores_prompt_in_metadata(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1", "prompt": "add a new endpoint"})
        assert state["metadata"]["prompt"] == "add a new endpoint"

    def test_initial_state_stores_plan_name_in_metadata(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1", "planName": "my_plan"})
        assert state["metadata"]["plan_name"] == "my_plan"

    def test_initial_state_plan_is_empty_dict(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["plan"] == {}

    def test_initial_state_code_is_empty_dict(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["code"] == {}

    def test_initial_state_handles_missing_task_id(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({})
        assert state["task_id"] == ""
        assert state["intent"] == "code_change"


# ---------------------------------------------------------------------------
# run() output format tests
# ---------------------------------------------------------------------------

class TestCodeChangeWorkflowRun:
    """Tests for CodeChangeWorkflow.run output format."""

    def test_run_returns_dict_with_metadata_key(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        assert "metadata" in result

    def test_run_metadata_contains_code_change_result(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        assert "code_change_result" in result["metadata"]

    def test_run_code_change_result_has_intent_key(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert "intent" in code_change_result

    def test_run_code_change_result_intent_is_code_change(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["intent"] == "code_change"

    def test_run_code_change_result_has_result_key(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert "result" in code_change_result

    def test_run_code_change_result_has_success_key(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert "success" in code_change_result

    def test_run_code_change_result_has_changes_key(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert "changes" in code_change_result

    def test_run_code_change_result_has_execution_path_key(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert "executionPath" in code_change_result

    def test_run_code_change_result_execution_path_is_langgraph(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["executionPath"] == "langgraph"

    def test_run_code_change_result_success_is_bool(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert isinstance(code_change_result["success"], bool)

    def test_run_code_change_result_changes_is_list(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert isinstance(code_change_result["changes"], list)

    def test_run_code_change_result_result_is_applied_on_success(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("def new_func(): pass"))
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["result"] == "applied"
        assert code_change_result["success"] is True

    def test_run_stage_is_completed_on_success(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("def new_func(): pass"))
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        assert result["stage"] == WORKFLOW_STAGE_COMPLETED

    def test_run_uses_llm_client_for_generation(self):
        mock_llm = _make_mock_llm("def new_func(): pass")
        wf = CodeChangeWorkflow(llm_client=mock_llm)
        wf.run({"task_id": "t1", "prompt": "add a new function"})
        mock_llm.generate.assert_called_once()

    def test_run_preserves_task_id_in_state(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "my-task-123", "prompt": "fix the bug"})
        assert result["task_id"] == "my-task-123"

    def test_run_classifies_addition_change_type(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("new code"))
        result = wf.run({"task_id": "t1", "prompt": "add a new endpoint"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["change_type"] == "addition"

    def test_run_classifies_bugfix_change_type(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("fixed code"))
        result = wf.run({"task_id": "t1", "prompt": "fix the null pointer bug"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["change_type"] == "bugfix"

    def test_run_classifies_refactor_change_type(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("refactored code"))
        result = wf.run({"task_id": "t1", "prompt": "refactor the authentication module"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["change_type"] == "refactor"

    def test_run_preserves_plan_name(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        result = wf.run({"task_id": "t1", "prompt": "add feature", "planName": "my_plan"})
        code_change_result = result["metadata"]["code_change_result"]
        assert code_change_result["planName"] == "my_plan"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestCodeChangeWorkflowErrorHandling:
    """Tests for error handling in CodeChangeWorkflow."""

    def test_run_llm_failure_results_in_failed_state(self):
        """When LLM raises, workflow should fail after exhausting retries."""
        wf = CodeChangeWorkflow(
            llm_client=_make_failing_llm(),
            max_retries=0,  # no retries for fast test
        )
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        assert result["stage"] == WORKFLOW_STAGE_FAILED

    def test_run_llm_failure_records_error(self):
        """When LLM raises, the error should be recorded in state."""
        wf = CodeChangeWorkflow(
            llm_client=_make_failing_llm(),
            max_retries=0,
        )
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        assert len(result["errors"]) >= 1

    def test_run_llm_failure_error_is_retryable(self):
        """LLM errors should be classified as retryable."""
        wf = CodeChangeWorkflow(
            llm_client=_make_failing_llm(),
            max_retries=0,
        )
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        # The error record should indicate retryable=True
        errors = result.get("errors", [])
        assert len(errors) >= 1
        assert errors[-1].get("retryable") is True

    def test_run_llm_failure_retries_up_to_max(self):
        """When LLM fails, workflow should retry up to max_retries times."""
        mock_llm = _make_failing_llm()
        wf = CodeChangeWorkflow(llm_client=mock_llm, max_retries=2)
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        # Should have attempted 3 times (1 initial + 2 retries)
        assert mock_llm.generate.call_count == 3
        assert result["stage"] == WORKFLOW_STAGE_FAILED

    def test_run_empty_prompt_produces_failed_result(self):
        """When prompt is empty, no LLM call is made and result is failed."""
        mock_llm = _make_mock_llm()
        wf = CodeChangeWorkflow(llm_client=mock_llm)
        result = wf.run({"task_id": "t1", "prompt": ""})
        # No LLM call for empty prompt
        mock_llm.generate.assert_not_called()
        # Result should be failed (no changes generated)
        code_change_result = result["metadata"].get("code_change_result", {})
        assert code_change_result.get("result") == "failed"
        assert code_change_result.get("success") is False

    def test_run_llm_failure_with_retries_exhausted_records_multiple_errors(self):
        """After exhausting retries, multiple error records should exist."""
        wf = CodeChangeWorkflow(
            llm_client=_make_failing_llm(),
            max_retries=1,
        )
        result = wf.run({"task_id": "t1", "prompt": "add a new function"})
        assert result["stage"] == WORKFLOW_STAGE_FAILED
        assert len(result["errors"]) >= 1


# ---------------------------------------------------------------------------
# get_code_change_result() tests
# ---------------------------------------------------------------------------

class TestGetCodeChangeResult:
    """Tests for CodeChangeWorkflow.get_code_change_result()."""

    def test_get_code_change_result_returns_dict(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        result = wf.get_code_change_result(final_state)
        assert isinstance(result, dict)

    def test_get_code_change_result_intent_is_code_change(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        result = wf.get_code_change_result(final_state)
        assert result.get("intent") == "code_change"

    def test_get_code_change_result_has_execution_path(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        result = wf.get_code_change_result(final_state)
        assert result.get("executionPath") == "langgraph"

    def test_get_code_change_result_has_success_field(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        result = wf.get_code_change_result(final_state)
        assert "success" in result

    def test_get_code_change_result_has_changes_field(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        result = wf.get_code_change_result(final_state)
        assert "changes" in result

    def test_get_code_change_result_returns_empty_dict_for_empty_state(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        empty_state = {"task_id": "t1", "metadata": {}}
        result = wf.get_code_change_result(empty_state)  # type: ignore[arg-type]
        assert result == {}

    def test_get_code_change_result_returns_empty_dict_for_no_metadata(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        empty_state = {"task_id": "t1"}
        result = wf.get_code_change_result(empty_state)  # type: ignore[arg-type]
        assert result == {}


# ---------------------------------------------------------------------------
# get_memory_record() tests
# ---------------------------------------------------------------------------

class TestGetMemoryRecord:
    """Tests for CodeChangeWorkflow.get_memory_record()."""

    def test_get_memory_record_returns_dict(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        record = wf.get_memory_record(final_state)
        assert isinstance(record, dict)

    def test_get_memory_record_intent_is_code_change(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        record = wf.get_memory_record(final_state)
        assert record.get("intent") == "code_change"

    def test_get_memory_record_has_execution_path(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        record = wf.get_memory_record(final_state)
        assert record.get("executionPath") == "langgraph"

    def test_get_memory_record_has_status_done(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        record = wf.get_memory_record(final_state)
        assert record.get("status") == "done"

    def test_get_memory_record_has_result_field(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm("code"))
        final_state = wf.run({"task_id": "t1", "prompt": "add feature"})
        record = wf.get_memory_record(final_state)
        assert "result" in record

    def test_get_memory_record_returns_empty_dict_for_empty_state(self):
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        empty_state = {"task_id": "t1", "metadata": {}}
        record = wf.get_memory_record(empty_state)  # type: ignore[arg-type]
        assert record == {}


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Strategies
_task_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=64,
)
_prompt_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" _-.,"),
    min_size=1,
    max_size=200,
)
_plan_name_strategy = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
        min_size=1,
        max_size=50,
    ),
)


class TestPropertyCodeChangeWorkflow:
    """
    **Property: Code Change Workflow Output Consistency**

    For any task_id and prompt, run() always returns a WorkflowState whose
    ``metadata["code_change_result"]["intent"]`` equals "code_change".

    **Validates: Requirements 8.3**
    """

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_always_returns_code_change_intent(
        self, task_id: str, prompt: str
    ):
        """
        **Property: For any task_id and prompt, run() always returns a dict
        with metadata["code_change_result"]["intent"] == "code_change".**

        **Validates: Requirements 8.3**
        """
        mock_llm = _make_mock_llm(f"change for: {prompt[:50]}")
        wf = CodeChangeWorkflow(llm_client=mock_llm)
        result = wf.run({"task_id": task_id, "prompt": prompt})

        # The result must always have metadata
        assert "metadata" in result

        # get_code_change_result must always return a dict with intent == "code_change"
        code_change_result = wf.get_code_change_result(result)
        assert isinstance(code_change_result, dict)
        assert code_change_result.get("intent") == "code_change"

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_always_returns_langgraph_execution_path(
        self, task_id: str, prompt: str
    ):
        """
        **Property: For any task_id and prompt, run() always returns
        executionPath == "langgraph".**

        **Validates: Requirements 8.3**
        """
        mock_llm = _make_mock_llm(f"change for: {prompt[:50]}")
        wf = CodeChangeWorkflow(llm_client=mock_llm)
        result = wf.run({"task_id": task_id, "prompt": prompt})

        code_change_result = wf.get_code_change_result(result)
        assert code_change_result.get("executionPath") == "langgraph"

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_result_has_required_keys(
        self, task_id: str, prompt: str
    ):
        """
        **Property: For any task_id and prompt, the code_change_result always
        contains the required keys: intent, result, success, changes, executionPath.**

        **Validates: Requirements 8.3**
        """
        mock_llm = _make_mock_llm(f"change for: {prompt[:50]}")
        wf = CodeChangeWorkflow(llm_client=mock_llm)
        result = wf.run({"task_id": task_id, "prompt": prompt})

        code_change_result = wf.get_code_change_result(result)
        required_keys = {"intent", "result", "success", "changes", "executionPath"}
        assert required_keys.issubset(code_change_result.keys())

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_initial_state_always_has_code_change_intent(
        self, task_id: str, prompt: str
    ):
        """
        **Property: For any task_id and prompt, get_initial_state always
        returns a state with intent == "code_change".**

        **Validates: Requirements 8.3**
        """
        wf = CodeChangeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": task_id, "prompt": prompt})
        assert state["intent"] == "code_change"
        assert state["task_id"] == task_id
        assert state["retry_count"] == 0
        assert state["errors"] == []
        assert state["stage"] == WORKFLOW_STAGE_INIT

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_llm_failure_always_produces_failed_state(
        self, task_id: str, prompt: str
    ):
        """
        **Property: For any task_id and prompt, when LLM always fails,
        run() always returns a failed state.**

        **Validates: Requirements 8.6**
        """
        wf = CodeChangeWorkflow(
            llm_client=_make_failing_llm(),
            max_retries=0,
        )
        result = wf.run({"task_id": task_id, "prompt": prompt})
        assert result["stage"] == WORKFLOW_STAGE_FAILED
        assert len(result["errors"]) >= 1
