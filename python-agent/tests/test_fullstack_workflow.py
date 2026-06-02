"""
Unit and property-based tests for FullstackWorkflow.

Task 23.2: Implement fullstack generation LangGraph workflow

Tests cover:
- FullstackWorkflow: initial state (task_id, intent, stage, retry_count, errors)
- run() output format (required keys, executionPath, success)
- FullstackGenerator integration (mock it)
- Error handling (generator failure -> graceful degradation)
- Property test: for any task_id/prompt, run() always returns a dict with
  intent == "fullstack_generation"

**Validates: Requirements 8.3**
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from generators.fullstack_generator import FullstackGenerator
from workflows.base_workflow import (
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
)
from workflows.fullstack_workflow import FullstackWorkflow
from utils.errors import LLMError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_FRONTEND_FILES = {
    "frontend/index.html": "<html></html>",
    "frontend/styles.css": "body {}",
    "frontend/app.js": "// app",
    "frontend/api-config.js": "// config",
}

_DEFAULT_BACKEND_FILES = {
    "backend/app.py": "# Flask app",
    "backend/models.py": "# models",
    "backend/database.py": "# db",
    "requirements.txt": "flask==3.0.3",
    "README.generated.md": "# readme",
    "docker-compose.yml": "version: '3.8'",
    ".env.example": "FLASK_ENV=development",
}

_DEFAULT_FILES = {**_DEFAULT_FRONTEND_FILES, **_DEFAULT_BACKEND_FILES}


def _make_mock_generator(files: dict | None = None) -> MagicMock:
    if files is None:
        files = _DEFAULT_FILES
    mock = MagicMock(spec=FullstackGenerator)
    result = MagicMock()
    result.files = files
    result.used_fallback = False
    result.reason = "fullstack_template_generated"
    mock.generate.return_value = result
    return mock


def _make_failing_generator(exc: Exception | None = None) -> MagicMock:
    if exc is None:
        exc = RuntimeError("Generator unavailable")
    mock = MagicMock(spec=FullstackGenerator)
    mock.generate.side_effect = exc
    return mock


def _make_workflow(
    generator: MagicMock | None = None,
    **kwargs: Any,
) -> FullstackWorkflow:
    return FullstackWorkflow(
        fullstack_generator=generator or _make_mock_generator(),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Initial state tests
# ---------------------------------------------------------------------------

class TestFullstackWorkflowInitialState:

    def test_initial_state_sets_task_id(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "task-abc"})
        assert state["task_id"] == "task-abc"

    def test_initial_state_sets_intent_to_fullstack_generation(self):
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["intent"] == "fullstack_generation"

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
        assert state["intent"] == "fullstack_generation"


# ---------------------------------------------------------------------------
# run() output format tests
# ---------------------------------------------------------------------------

class TestFullstackWorkflowRun:

    def test_run_returns_dict_with_metadata_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert "metadata" in result

    def test_run_metadata_contains_fullstack_generation_result(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert "fullstack_generation_result" in result["metadata"]

    def test_run_result_has_intent_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "intent" in fs_result

    def test_run_result_intent_is_fullstack_generation(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["intent"] == "fullstack_generation"

    def test_run_result_has_result_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "result" in fs_result

    def test_run_result_has_success_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "success" in fs_result

    def test_run_result_has_framework_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "framework" in fs_result

    def test_run_result_has_frontend_files_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "frontend_files" in fs_result

    def test_run_result_has_backend_files_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "backend_files" in fs_result

    def test_run_result_has_all_files_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "all_files" in fs_result

    def test_run_result_has_execution_path_key(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert "executionPath" in fs_result

    def test_run_result_execution_path_is_langgraph(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["executionPath"] == "langgraph"

    def test_run_result_success_is_bool(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert isinstance(fs_result["success"], bool)

    def test_run_result_frontend_files_is_list(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert isinstance(fs_result["frontend_files"], list)

    def test_run_result_backend_files_is_list(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert isinstance(fs_result["backend_files"], list)

    def test_run_result_all_files_is_list(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert isinstance(fs_result["all_files"], list)

    def test_run_result_is_generated_on_success(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["result"] == "generated"
        assert fs_result["success"] is True

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
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["framework"] == "flask"

    def test_run_framework_fastapi_in_result(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app", "framework": "fastapi"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["framework"] == "fastapi"

    def test_run_frontend_files_contains_frontend_paths(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        for f in fs_result["frontend_files"]:
            assert f.startswith("frontend/")

    def test_run_backend_files_does_not_contain_frontend_paths(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        for f in fs_result["backend_files"]:
            assert not f.startswith("frontend/")

    def test_run_all_files_is_union_of_frontend_and_backend(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        combined = set(fs_result["frontend_files"]) | set(fs_result["backend_files"])
        assert combined == set(fs_result["all_files"])

    def test_run_preserves_plan_name(self):
        wf = _make_workflow()
        result = wf.run({"task_id": "t1", "prompt": "build a todo app", "planName": "my_plan"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["planName"] == "my_plan"


# ---------------------------------------------------------------------------
# FullstackGenerator integration tests
# ---------------------------------------------------------------------------

class TestFullstackGeneratorIntegration:

    def test_run_calls_fullstack_generator_with_prompt(self):
        mock_gen = _make_mock_generator()
        wf = _make_workflow(generator=mock_gen)
        wf.run({"task_id": "t1", "prompt": "build a todo app"})
        mock_gen.generate.assert_called_once()
        call_args = mock_gen.generate.call_args
        assert call_args[0][0] == "build a todo app"

    def test_run_uses_injected_fullstack_generator(self):
        mock_gen = _make_mock_generator()
        wf = _make_workflow(generator=mock_gen)
        wf.run({"task_id": "t1", "prompt": "build a blog"})
        assert mock_gen.generate.called

    def test_run_stores_generated_files_in_code(self):
        files = {
            "frontend/index.html": "<html></html>",
            "backend/app.py": "# app",
            "requirements.txt": "flask",
        }
        mock_gen = _make_mock_generator(files=files)
        wf = _make_workflow(generator=mock_gen)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert "frontend/index.html" in result["code"]
        assert "backend/app.py" in result["code"]
        assert "requirements.txt" in result["code"]

    def test_run_passes_raw_task_to_generator(self):
        mock_gen = _make_mock_generator()
        wf = _make_workflow(generator=mock_gen)
        task = {"task_id": "t1", "prompt": "build a todo app", "extra": "data"}
        wf.run(task)
        call_kwargs = mock_gen.generate.call_args[1]
        assert "task" in call_kwargs
        assert call_kwargs["task"]["task_id"] == "t1"

    def test_run_only_frontend_files_results_in_failed(self):
        # If generator only returns frontend files, validation should fail
        frontend_only = {
            "frontend/index.html": "<html></html>",
            "frontend/app.js": "// app",
        }
        mock_gen = _make_mock_generator(files=frontend_only)
        wf = _make_workflow(generator=mock_gen)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["result"] == "failed"
        assert fs_result["success"] is False

    def test_run_only_backend_files_results_in_failed(self):
        # If generator only returns backend files, validation should fail
        backend_only = {
            "backend/app.py": "# app",
            "requirements.txt": "flask",
        }
        mock_gen = _make_mock_generator(files=backend_only)
        wf = _make_workflow(generator=mock_gen)
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        fs_result = result["metadata"]["fullstack_generation_result"]
        assert fs_result["result"] == "failed"
        assert fs_result["success"] is False


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestFullstackWorkflowErrorHandling:

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
        mock_gen.generate.assert_called_once()

    def test_run_generator_failure_graceful_degradation_no_exception_raised(self):
        """Generator failure should not propagate as an exception to the caller."""
        wf = _make_workflow(
            generator=_make_failing_generator(),
            max_retries=0,
        )
        # Should not raise
        result = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_fullstack_generation_result() tests
# ---------------------------------------------------------------------------

class TestGetFullstackGenerationResult:

    def test_get_fullstack_generation_result_returns_dict(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert isinstance(result, dict)

    def test_get_fullstack_generation_result_intent_is_fullstack_generation(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert result.get("intent") == "fullstack_generation"

    def test_get_fullstack_generation_result_has_execution_path(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert result.get("executionPath") == "langgraph"

    def test_get_fullstack_generation_result_has_success_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert "success" in result

    def test_get_fullstack_generation_result_has_frontend_files_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert "frontend_files" in result

    def test_get_fullstack_generation_result_has_backend_files_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert "backend_files" in result

    def test_get_fullstack_generation_result_has_all_files_field(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        result = wf.get_fullstack_generation_result(final_state)
        assert "all_files" in result

    def test_get_fullstack_generation_result_returns_empty_dict_for_empty_state(self):
        wf = _make_workflow()
        empty_state = {"task_id": "t1", "metadata": {}}
        result = wf.get_fullstack_generation_result(empty_state)
        assert result == {}

    def test_get_fullstack_generation_result_returns_empty_dict_for_no_metadata(self):
        wf = _make_workflow()
        empty_state = {"task_id": "t1"}
        result = wf.get_fullstack_generation_result(empty_state)
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

    def test_get_memory_record_intent_is_fullstack_generation(self):
        wf = _make_workflow()
        final_state = wf.run({"task_id": "t1", "prompt": "build a todo app"})
        record = wf.get_memory_record(final_state)
        assert record.get("intent") == "fullstack_generation"

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


class TestPropertyFullstackWorkflow:
    """
    Property: Fullstack Generation Workflow Output Consistency

    For any task_id and prompt, run() always returns a WorkflowState whose
    metadata["fullstack_generation_result"]["intent"] equals "fullstack_generation".

    **Validates: Requirements 8.3**
    """

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_always_returns_fullstack_generation_intent(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, run() always returns a dict
        with metadata["fullstack_generation_result"]["intent"] == "fullstack_generation".

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        result = wf.run({"task_id": task_id, "prompt": prompt})

        assert "metadata" in result
        fs_result = wf.get_fullstack_generation_result(result)
        assert isinstance(fs_result, dict)
        assert fs_result.get("intent") == "fullstack_generation"

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
        fs_result = wf.get_fullstack_generation_result(result)
        assert fs_result.get("executionPath") == "langgraph"

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_run_result_has_required_keys(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, the fullstack_generation_result always
        contains the required keys: intent, result, success, framework,
        frontend_files, backend_files, all_files, executionPath.

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        result = wf.run({"task_id": task_id, "prompt": prompt})
        fs_result = wf.get_fullstack_generation_result(result)
        required_keys = {
            "intent", "result", "success", "framework",
            "frontend_files", "backend_files", "all_files", "executionPath",
        }
        assert required_keys.issubset(fs_result.keys())

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_initial_state_always_has_fullstack_generation_intent(
        self, task_id: str, prompt: str
    ):
        """
        Property: For any task_id and prompt, get_initial_state always
        returns a state with intent == "fullstack_generation".

        **Validates: Requirements 8.3**
        """
        wf = _make_workflow()
        state = wf.get_initial_state({"task_id": task_id, "prompt": prompt})
        assert state["intent"] == "fullstack_generation"
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
        Property: For any task_id and prompt, when FullstackGenerator always fails,
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
