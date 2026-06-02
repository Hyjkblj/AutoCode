"""
Unit and property-based tests for BackendGenerationWorkflow.

Task 23.1: Implement backend generation LangGraph workflow

Tests cover:
- BackendGenerationWorkflow: initial state (task_id, intent, stage, retry_count, errors)
- run() output format (required keys, executionPath, success)
- BackendGenerator integration (mock it)
- ValidationGate integration (mock it)
- Error handling (generator failure -> graceful degradation)
- Property test: for any task_id/prompt, run() always returns a dict with
  intent == "backend_generation"

**Validates: Requirements 8.3**
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from generators.backend_generator import BackendGenerator
from generators.validation_gate import ValidationGate, ValidationResult
from generators.fix_loop import FixLoop, FixResult
from workflows.base_workflow import (
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
)
from workflows.backend_generation_workflow import BackendGenerationWorkflow
from utils.errors import LLMError, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_generator(files: dict | None = None) -> MagicMock:
    if files is None:
        files = {
            "backend/app.py": "# Flask app",
            "backend/models.py": "# models",
            "requirements.txt": "flask==3.0.3",
            "README.generated.md": "# readme",
        }
    mock = MagicMock(spec=BackendGenerator)
    result = MagicMock()
    result.files = files
    result.used_fallback = True
    result.reason = "backend_template_generated"
    mock.generate.return_value = result
    return mock


def _make_failing_generator(exc: Exception | None = None) -> MagicMock:
    if exc is None:
        exc = RuntimeError("Generator unavailable")
    mock = MagicMock(spec=BackendGenerator)
    mock.generate.side_effect = exc
    return mock


def _make_mock_validation_gate(ok: bool = True, errors: list | None = None) -> MagicMock:
    mock = MagicMock(spec=ValidationGate)
    mock.validate.return_value = ValidationResult(ok=ok, errors=errors or [])
    return mock


def _make_mock_fix_loop(success: bool = True) -> MagicMock:
    mock = MagicMock(spec=FixLoop)
    fix_result = MagicMock(spec=FixResult)
    fix_result.success = success
    fix_result.iterations_used = 1 if success else 3
    fix_result.final_errors = [] if success else ["fix failed"]
    mock.fix_and_validate.return_value = fix_result
    return mock


def _make_workflow(
    generator: MagicMock | None = None,
    validation_gate: MagicMock | None = None,
    fix_loop: MagicMock | None = None,
    **kwargs: Any,
) -> BackendGenerationWorkflow:
    return BackendGenerationWorkflow(
        backend_generator=generator or _make_mock_generator(),
        validation_gate=validation_gate or _make_mock_validation_gate(ok=True),
        fix_loop=fix_loop or _make_mock_fix_loop(success=True),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Initial state tests
# ---------------------------------------------------------------------------

class TestBackendGenerationWorkflowInitialState:

    def test_initial_state_sets_task_id(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "task-abc"})
        assert state["task_id"] == "task-abc"

    def test_initial_state_sets_intent_to_backend_generation(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["intent"] == "backend_generation"

    def test_initial_state_stage_is_init(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["stage"] == WORKFLOW_STAGE_INIT

    def test_initial_state_retry_count_is_zero(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["retry_count"] == 0

    def test_initial_state_errors_is_empty(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["errors"] == []

    def test_initial_state_stores_prompt_in_metadata(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1", "prompt": "build a todo app"})
        assert state["metadata"]["prompt"] == "build a todo app"

    def test_initial_state_stores_framework_in_metadata(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1", "framework": "fastapi"})
        assert state["metadata"]["framework"] == "fastapi"

    def test_initial_state_defaults_framework_to_flask(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["metadata"]["framework"] == "flask"

    def test_initial_state_stores_plan_name_in_metadata(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1", "planName": "my_plan"})
        assert state["metadata"]["plan_name"] == "my_plan"

    def test_initial_state_plan_is_empty_dict(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["plan"] == {}

    def test_initial_state_code_is_empty_dict(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["code"] == {}

    def test_initial_state_handles_missing_task_id(self):
        wf = _make_workflow()
        state = wf.get_initial_state({})
        assert state["task_id"] == ""
        assert state["intent"] == "backend_generation"


# ---------------------------------------------------------------------------
# run() output format tests
# ---------------------------------------------------------------------------

class TestBackendGenerationWorkflowRun:

    def test_run_returns_dict_with_metadata_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert "metadata" in result

    def test_run_metadata_contains_backend_generation_result(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert "backend_generation_result" in result["metadata"]

    def test_run_result_has_intent_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert "intent" in bg_result

    def test_run_result_intent_is_backend_generation(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["intent"] == "backend_generation"

    def test_run_result_has_result_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert "result" in bg_result

    def test_run_result_has_success_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert "success" in bg_result

    def test_run_result_has_framework_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert "framework" in bg_result

    def test_run_result_has_files_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert "files" in bg_result

    def test_run_result_has_execution_path_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert "executionPath" in bg_result

    def test_run_result_execution_path_is_langgraph(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["executionPath"] == "langgraph"

    def test_run_result_success_is_bool(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert isinstance(bg_result["success"], bool)

    def test_run_result_files_is_list(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert isinstance(bg_result["files"], list)

    def test_run_result_is_generated_on_success(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["result"] == "generated"
        assert bg_result["success"] is True

    def test_run_stage_is_completed_on_success(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert result["stage"] == WORKFLOW_STAGE_COMPLETED

    def test_run_preserves_task_id_in_state(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "my-task-123", "prompt": "build a blog"})
        assert result["task_id"] == "my-task-123"

    def test_run_framework_flask_in_result(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app", "framework": "flask"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["framework"] == "flask"

    def test_run_framework_fastapi_in_result(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app", "framework": "fastapi"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["framework"] == "fastapi"

    def test_run_files_list_contains_generated_file_names(self):
        files = {
            "backend/app.py": "# app",
            "backend/models.py": "# models",
            "requirements.txt": "flask==3.0.3",
        }
        wf = _make_workflow(generator=_make_mock_generator(files=files))
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert set(bg_result["files"]) == set(files.keys())

    def test_run_preserves_plan_name(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app", "planName": "my_plan"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["planName"] == "my_plan"


# ---------------------------------------------------------------------------
# BackendGenerator integration tests
# ---------------------------------------------------------------------------

class TestBackendGeneratorIntegration:

    def test_run_calls_backend_generator_with_prompt(self):
        mock_gen = _make_mock_generator()
        wf = _make_workflow(generator=mock_gen)
        wf.run({"task_id": "t1", "prompt": "build a todo app"})
        mock_gen.generate.assert_called_once_with("build a todo app")

    def test_run_uses_injected_backend_generator(self):
        mock_gen = _make_mock_generator()
        wf = _make_workflow(generator=mock_gen)
        wf.run({"task_id": "t1", "prompt": "build a blog"})
        assert mock_gen.generate.called

    def test_run_stores_generated_files_in_code(self):
        files = {"backend/app.py": "# app", "requirements.txt": "flask"}
        mock_gen = _make_mock_generator(files=files)
        wf = _make_workflow(generator=mock_gen)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert "backend/app.py" in result["code"]
        assert "requirements.txt" in result["code"]


# ---------------------------------------------------------------------------
# ValidationGate integration tests
# ---------------------------------------------------------------------------

class TestValidationGateIntegration:

    def test_run_calls_validation_gate(self):
        mock_vg = _make_mock_validation_gate(ok=True)
        wf = _make_workflow(validation_gate=mock_vg)
        wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert mock_vg.validate.called

    def test_run_validation_failure_triggers_fix_loop(self):
        mock_vg = _make_mock_validation_gate(ok=False, errors=["missing file"])
        mock_fl = _make_mock_fix_loop(success=True)
        wf = _make_workflow(validation_gate=mock_vg, fix_loop=mock_fl)
        wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert mock_fl.fix_and_validate.called

    def test_run_validation_success_skips_fix_loop(self):
        mock_vg = _make_mock_validation_gate(ok=True)
        mock_fl = _make_mock_fix_loop(success=True)
        wf = _make_workflow(validation_gate=mock_vg, fix_loop=mock_fl)
        wf.run({"task_id": "t1", "prompt": "build a todo app"})
        mock_fl.fix_and_validate.assert_not_called()

    def test_run_fix_loop_failure_results_in_failed_result(self):
        mock_vg = _make_mock_validation_gate(ok=False, errors=["syntax error"])
        mock_fl = _make_mock_fix_loop(success=False)
        wf = _make_workflow(validation_gate=mock_vg, fix_loop=mock_fl)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["result"] == "failed"
        assert bg_result["success"] is False

    def test_run_fix_loop_success_results_in_generated_result(self):
        mock_vg = _make_mock_validation_gate(ok=False, errors=["minor error"])
        mock_fl = _make_mock_fix_loop(success=True)
        wf = _make_workflow(validation_gate=mock_vg, fix_loop=mock_fl)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        bg_result = result["metadata"]["backend_generation_result"]
        assert bg_result["result"] == "generated"
        assert bg_result["success"] is True


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestBackendGenerationWorkflowErrorHandling:

    def test_run_generator_failure_results_in_failed_state(self):
        wf = _make_workflow(
            generator=_make_failing_generator(),
            max_retries=0,
        )
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert result["stage"] == WORKFLOW_STAGE_FAILED

    def test_run_generator_failure_records_error(self):
        wf = _make_workflow(
            generator=_make_failing_generator(),
            max_retries=0,
        )
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert len(result["errors"]) >= 1

    def test_run_generator_failure_error_is_retryable(self):
        wf = _make_workflow(
            generator=_make_failing_generator(),
            max_retries=0,
        )
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        errors = result.get("errors", [])
        assert len(errors) >= 1
        assert errors[-1].get("retryable") is True

    def test_run_generator_failure_retries_up_to_max(self):
        mock_gen = _make_failing_generator()
        wf = _make_workflow(generator=mock_gen, max_retries=2)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert mock_gen.generate.call_count == 3
        assert result["stage"] == WORKFLOW_STAGE_FAILED

    def test_run_empty_prompt_still_calls_generator(self):
        mock_gen = _make_mock_generator()
        wf = _make_workflow(generator=mock_gen)
        wf.run({"task_id": "t1", "prompt": ""})
        mock_gen.generate.assert_called_once_with("")


# ---------------------------------------------------------------------------
# get_backend_generation_result() tests
# ---------------------------------------------------------------------------

class TestGetBackendGenerationResult:

    def test_get_backend_generation_result_returns_dict(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_backend_generation_result(final_state)
        assert isinstance(result, dict)

    def test_get_backend_generation_result_intent_is_backend_generation(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_backend_generation_result(final_state)
        assert result.get("intent") == "backend_generation"

    def test_get_backend_generation_result_has_execution_path(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_backend_generation_result(final_state)
        assert result.get("executionPath") == "langgraph"

    def test_get_backend_generation_result_has_success_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_backend_generation_result(final_state)
        assert "success" in result

    def test_get_backend_generation_result_has_files_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_backend_generation_result(final_state)
        assert "files" in result

    def test_get_backend_generation_result_returns_empty_dict_for_empty_state(self):
        wf = _make_workflow()
        empty_state = {"task_id": "t1", "metadata": {}}
        result = wf.get_backend_generation_result(empty_state)
        assert result == {}

    def test_get_backend_generation_result_returns_empty_dict_for_no_metadata(self):
        wf = _make_workflow()
        empty_state = {"task_id": "t1"}
        result = wf.get_backend_generation_result(empty_state)
        assert result == {}


# ---------------------------------------------------------------------------
# get_memory_record() tests
# ---------------------------------------------------------------------------

class TestGetMemoryRecord:

    def test_get_memory_record_returns_dict(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        record = wf.get_memory_record(final_state)
        assert isinstance(record, dict)

    def test_get_memory_record_intent_is_backend_generation(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        record = wf.get_memory_record(final_state)
        assert record.get("intent") == "backend_generation"

    def test_get_memory_record_has_execution_path(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        record = wf.get_memory_record(final_state)
        assert record.get("executionPath") == "langgraph"

    def test_get_memory_record_has_status_done(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        record = wf.get_memory_record(final_state)
        assert record.get("status") == "done"

    def test_get_memory_record_has_result_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        record = wf.get_memory_record(final_state)
        assert "result" in record

    def test_get_memory_record_returns_empty_dict_for_empty_state(self):
        wf = _make_workflow()
        empty_state = {"task_id": "t1", "metadata": {}}
        record = wf.get_memory_record(empty_state)
        assert record == {}


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

_task_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=64,
)
_prompt_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" _-.,"),
    min_size=0,
    max_size=200,
)


class TestPropertyBackendGenerationWorkflow:
    """
    Property: Backend Generation Workflow Output Consistency

    For any task_id and prompt, run() always returns a WorkflowState whose
    metadata["backend_generation_result"]["intent"] equals "backend_generation".

    **Validates: Requirements 8.3**
    """

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_always_returns_backend_generation_intent(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, run() always returns a dict
        with metadata["backend_generation_result"]["intent"] == "backend_generation".

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        result = wf.run({"task_id": task_id, "prompt": prompt})

        assert "metadata" in result
        bg_result = wf.get_backend_generation_result(result)
        assert isinstance(bg_result, dict)
        assert bg_result.get("intent") == "backend_generation"

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_always_returns_langgraph_execution_path(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, run() always returns
        executionPath == "langgraph".

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        result = wf.run({"task_id": task_id, "prompt": prompt})
        bg_result = wf.get_backend_generation_result(result)
        assert bg_result.get("executionPath") == "langgraph"

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_result_has_required_keys(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, the backend_generation_result always
        contains the required keys: intent, result, success, framework, files, executionPath.

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        result = wf.run({"task_id": task_id, "prompt": prompt})
        bg_result = wf.get_backend_generation_result(result)
        required_keys = {"intent", "result", "success", "framework", "files", "executionPath"}
        assert required_keys.issubset(bg_result.keys())

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_initial_state_always_has_backend_generation_intent(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, get_initial_state always
        returns a state with intent == "backend_generation".

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": task_id, "prompt": prompt})
        assert state["intent"] == "backend_generation"
        assert state["task_id"] == task_id
        assert state["retry_count"] == 0
        assert state["errors"] == []
        assert state["stage"] == WORKFLOW_STAGE_INIT

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_generator_failure_always_produces_failed_state(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, when BackendGenerator always fails,
        run() always returns a failed state.

        **Validates: Requirements 8.6**
        """
        wf = _make_workflow(
            generator=_make_failing_generator(),
            max_retries=0,
        )
        result = wf.run({"task_id": task_id, "prompt": prompt})
        assert result["stage"] == WORKFLOW_STAGE_FAILED
        assert len(result["errors"]) >= 1
