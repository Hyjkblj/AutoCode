"""
Unit and property-based tests for AnalyzeWorkflow, TestWorkflow, and
EngineComparisonFramework.

Task 21.2: Migrate analyze and test operations to LangGraph

Tests cover:
- AnalyzeWorkflow: graph nodes, initial state, run output
- TestWorkflow: graph nodes, initial state, run output (mocked sandbox)
- EngineComparisonFramework: compare(), compare_analyze(), compare_test()
- Property tests: identical results → consistency_score == 1.0
- Property tests: consistency_score always in [0.0, 1.0]

**Validates: Requirements 8.2, 8.4**
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from workflows.analyze_workflow import AnalyzeWorkflow
from workflows.base_workflow import (
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
)
from workflows.comparison_framework import (
    ComparisonResult,
    EngineComparisonFramework,
)
from workflows.test_workflow import TestWorkflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(response: str = "mock analysis response") -> MagicMock:
    """Return a mock LLMClient whose generate() returns *response*."""
    mock = MagicMock()
    mock.generate.return_value = response
    return mock


def _make_mock_exec_tool(ok: bool = True, status: str = "ok") -> MagicMock:
    """Return a mock ExecTool whose execute() returns a mock ExecResult."""
    from tools.exec_tool import ExecResult

    result = ExecResult(
        ok=ok,
        status=status,
        exit_code=0 if ok else 1,
        output="test output",
        retryable=False,
        reason=None if ok else "test_failed",
        tool="command.exec",
        tool_version="1.0",
        trace_id="trace-123",
        run_id="run-456",
        approval_id=None,
    )
    mock = MagicMock()
    mock.execute.return_value = result
    return mock


# ---------------------------------------------------------------------------
# AnalyzeWorkflow tests
# ---------------------------------------------------------------------------

class TestAnalyzeWorkflowInitialState:
    """Tests for AnalyzeWorkflow.get_initial_state."""

    def test_initial_state_sets_task_id(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "task-abc"})
        assert state["task_id"] == "task-abc"

    def test_initial_state_sets_intent_to_analyze(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["intent"] == "analyze"

    def test_initial_state_stage_is_init(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["stage"] == WORKFLOW_STAGE_INIT

    def test_initial_state_retry_count_is_zero(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["retry_count"] == 0

    def test_initial_state_errors_is_empty(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["errors"] == []

    def test_initial_state_stores_prompt_in_metadata(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1", "prompt": "analyze this code"})
        assert state["metadata"]["prompt"] == "analyze this code"

    def test_initial_state_stores_plan_name_in_metadata(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        state = wf.get_initial_state({"task_id": "t1", "planName": "my_plan"})
        assert state["metadata"]["plan_name"] == "my_plan"


class TestAnalyzeWorkflowRun:
    """Tests for AnalyzeWorkflow.run output format."""

    def test_run_returns_dict_with_required_keys(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze this"})
        # run() returns WorkflowState; check metadata contains analyze_result
        assert "metadata" in result
        analyze_result = result["metadata"].get("analyze_result", {})
        assert "intent" in analyze_result
        assert "result" in analyze_result

    def test_run_stage_is_completed_on_success(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze this"})
        assert result["stage"] == WORKFLOW_STAGE_COMPLETED

    def test_run_analyze_result_intent_is_analyze(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze this"})
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["intent"] == "analyze"

    def test_run_analyze_result_execution_path_is_langgraph(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze this"})
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["executionPath"] == "langgraph"

    def test_run_uses_llm_client_for_analysis(self):
        mock_llm = _make_mock_llm("step 1\nstep 2\nstep 3")
        wf = AnalyzeWorkflow(llm_client=mock_llm)
        wf.run({"task_id": "t1", "prompt": "analyze this code"})
        mock_llm.generate.assert_called_once()

    def test_run_get_analyze_result_returns_dict(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        final_state = wf.run({"task_id": "t1", "prompt": "analyze"})
        result = wf.get_analyze_result(final_state)
        assert isinstance(result, dict)
        assert result.get("intent") == "analyze"

    def test_run_get_memory_record_returns_dict(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        final_state = wf.run({"task_id": "t1", "prompt": "analyze"})
        record = wf.get_memory_record(final_state)
        assert isinstance(record, dict)
        assert record.get("intent") == "analyze"

    def test_run_classifies_test_sub_intent(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze test coverage"})
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["sub_intent"] == "test_analysis"

    def test_run_classifies_backend_sub_intent(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze the api routes"})
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["sub_intent"] == "backend_analysis"

    def test_run_classifies_general_sub_intent_for_unknown_prompt(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "do something"})
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["sub_intent"] == "general_analysis"

    def test_run_handles_llm_error_gracefully(self):
        """When LLM raises, workflow should still complete (with fallback)."""
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("LLM unavailable")
        wf = AnalyzeWorkflow(llm_client=mock_llm)
        result = wf.run({"task_id": "t1", "prompt": "analyze this"})
        # Should still complete (graceful degradation)
        assert result["stage"] == WORKFLOW_STAGE_COMPLETED
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["intent"] == "analyze"

    def test_run_preserves_plan_name(self):
        wf = AnalyzeWorkflow(llm_client=_make_mock_llm())
        result = wf.run({"task_id": "t1", "prompt": "analyze", "planName": "my_plan"})
        analyze_result = result["metadata"]["analyze_result"]
        assert analyze_result["planName"] == "my_plan"


# ---------------------------------------------------------------------------
# TestWorkflow tests
# ---------------------------------------------------------------------------

class TestTestWorkflowInitialState:
    """Tests for TestWorkflow.get_initial_state."""

    def test_initial_state_sets_task_id(self):
        wf = TestWorkflow(exec_tool=_make_mock_exec_tool())
        state = wf.get_initial_state({"task_id": "task-xyz"})
        assert state["task_id"] == "task-xyz"

    def test_initial_state_sets_intent_to_test(self):
        wf = TestWorkflow(exec_tool=_make_mock_exec_tool())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["intent"] == "test"

    def test_initial_state_stage_is_init(self):
        wf = TestWorkflow(exec_tool=_make_mock_exec_tool())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["stage"] == WORKFLOW_STAGE_INIT

    def test_initial_state_retry_count_is_zero(self):
        wf = TestWorkflow(exec_tool=_make_mock_exec_tool())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["retry_count"] == 0

    def test_initial_state_errors_is_empty(self):
        wf = TestWorkflow(exec_tool=_make_mock_exec_tool())
        state = wf.get_initial_state({"task_id": "t1"})
        assert state["errors"] == []

    def test_initial_state_stores_test_command_in_metadata(self):
        wf = TestWorkflow(exec_tool=_make_mock_exec_tool())
        state = wf.get_initial_state({"task_id": "t1", "testCommand": "pytest"})
        assert state["metadata"]["test_command"] == "pytest"


class TestTestWorkflowRun:
    """Tests for TestWorkflow.run output format."""

    def test_run_without_task_id_skips_sandbox(self):
        """When no taskId is present, sandbox is not called."""
        mock_exec = _make_mock_exec_tool()
        wf = TestWorkflow(exec_tool=mock_exec)
        result = wf.run({"task_id": "", "prompt": "run tests"})
        mock_exec.execute.assert_not_called()

    def test_run_with_task_id_calls_sandbox(self):
        """When taskId is present, sandbox execute is called."""
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        mock_exec.execute.assert_called_once()

    def test_run_successful_sandbox_sets_completed_stage(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        result = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        assert result["stage"] == WORKFLOW_STAGE_COMPLETED

    def test_run_failed_sandbox_sets_failed_stage(self):
        mock_exec = _make_mock_exec_tool(ok=False, status="test_failed")
        wf = TestWorkflow(exec_tool=mock_exec)
        result = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        assert result["stage"] == WORKFLOW_STAGE_FAILED

    def test_run_get_test_result_returns_dict(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        final_state = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        result = wf.get_test_result(final_state)
        assert isinstance(result, dict)
        assert result.get("intent") == "test"

    def test_run_get_memory_record_returns_dict(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        final_state = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        record = wf.get_memory_record(final_state)
        assert isinstance(record, dict)
        assert record.get("intent") == "test"

    def test_run_test_result_execution_path_is_langgraph(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        final_state = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        test_result = wf.get_test_result(final_state)
        assert test_result["executionPath"] == "langgraph"

    def test_run_successful_result_has_success_true(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        final_state = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        test_result = wf.get_test_result(final_state)
        assert test_result["success"] is True

    def test_run_failed_result_has_success_false(self):
        mock_exec = _make_mock_exec_tool(ok=False, status="test_failed")
        wf = TestWorkflow(exec_tool=mock_exec)
        final_state = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        test_result = wf.get_test_result(final_state)
        assert test_result["success"] is False

    def test_run_resolves_test_command_from_task(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        wf = TestWorkflow(exec_tool=mock_exec)
        final_state = wf.run({
            "task_id": "t1",
            "taskId": "t1",
            "prompt": "run tests",
            "testCommand": "pytest -v",
        })
        test_result = wf.get_test_result(final_state)
        assert test_result["command"] == "pytest -v"

    def test_run_handles_sandbox_exception_gracefully(self):
        """When sandbox raises, workflow should record the error and continue."""
        mock_exec = MagicMock()
        mock_exec.execute.side_effect = RuntimeError("sandbox unavailable")
        wf = TestWorkflow(exec_tool=mock_exec)
        result = wf.run({"task_id": "t1", "taskId": "t1", "prompt": "run tests"})
        # Should complete result_collection node even after sandbox failure
        assert "metadata" in result
        test_result = result["metadata"].get("test_result", {})
        assert test_result.get("intent") == "test"


# ---------------------------------------------------------------------------
# EngineComparisonFramework tests
# ---------------------------------------------------------------------------

class TestEngineComparisonFrameworkCompare:
    """Tests for EngineComparisonFramework.compare()."""

    def test_compare_identical_results_returns_consistent_true(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "analyze",
            {"intent": "analyze", "result": "planned"},
            {"intent": "analyze", "result": "planned"},
        )
        assert result.consistent is True

    def test_compare_identical_results_returns_score_1_0(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "analyze",
            {"intent": "analyze", "result": "planned"},
            {"intent": "analyze", "result": "planned"},
        )
        assert result.consistency_score == 1.0

    def test_compare_identical_results_returns_empty_discrepancies(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "analyze",
            {"intent": "analyze", "result": "planned"},
            {"intent": "analyze", "result": "planned"},
        )
        assert result.discrepancies == []

    def test_compare_different_results_returns_consistent_false(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "analyze",
            {"intent": "analyze", "result": "planned"},
            {"intent": "analyze", "result": "failed"},
        )
        assert result.consistent is False

    def test_compare_different_results_has_discrepancies(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "analyze",
            {"intent": "analyze", "result": "planned"},
            {"intent": "analyze", "result": "failed"},
        )
        assert len(result.discrepancies) > 0

    def test_compare_score_is_between_0_and_1(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "test",
            {"intent": "test", "result": "executed"},
            {"intent": "test", "result": "failed", "extra": "value"},
        )
        assert 0.0 <= result.consistency_score <= 1.0

    def test_compare_both_empty_returns_consistent_true(self):
        fw = EngineComparisonFramework()
        result = fw.compare("analyze", {}, {})
        assert result.consistent is True
        assert result.consistency_score == 1.0

    def test_compare_returns_comparison_result_instance(self):
        fw = EngineComparisonFramework()
        result = fw.compare("analyze", {"a": 1}, {"a": 1})
        assert isinstance(result, ComparisonResult)

    def test_compare_logs_discrepancies_at_warning(self, caplog):
        import logging
        fw = EngineComparisonFramework()
        with caplog.at_level(logging.WARNING):
            fw.compare(
                "analyze",
                {"intent": "analyze", "result": "planned"},
                {"intent": "analyze", "result": "failed"},
            )
        assert any("discrepancy" in record.message.lower() for record in caplog.records)

    def test_compare_one_has_error_key_detects_success_mismatch(self):
        fw = EngineComparisonFramework()
        result = fw.compare(
            "analyze",
            {"intent": "analyze", "result": "planned"},
            {"error": "something went wrong"},
        )
        assert result.consistent is False
        assert any("mismatch" in d.lower() for d in result.discrepancies)


class TestEngineComparisonFrameworkCompareAnalyze:
    """Tests for EngineComparisonFramework.compare_analyze()."""

    def test_compare_analyze_returns_metrics_with_intent_analyze(self):
        mock_llm = _make_mock_llm()
        analyze_wf = AnalyzeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(analyze_workflow=analyze_wf)
        metrics = fw.compare_analyze({"task_id": "t1", "prompt": "analyze this"})
        assert metrics.intent == "analyze"

    def test_compare_analyze_consistency_score_in_range(self):
        mock_llm = _make_mock_llm()
        analyze_wf = AnalyzeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(analyze_workflow=analyze_wf)
        metrics = fw.compare_analyze({"task_id": "t1", "prompt": "analyze this"})
        assert 0.0 <= metrics.output_consistency_score <= 1.0

    def test_compare_analyze_with_custom_legacy_handler(self):
        mock_llm = _make_mock_llm()
        analyze_wf = AnalyzeWorkflow(llm_client=mock_llm)

        def legacy_handler(task: dict) -> dict:
            return {
                "result": "planned",
                "intent": "analyze",
                "planName": task.get("planName", ""),
                "executionPath": "legacy",
            }

        fw = EngineComparisonFramework(
            analyze_workflow=analyze_wf,
            legacy_analyze_handler=legacy_handler,
        )
        metrics = fw.compare_analyze({"task_id": "t1", "prompt": "analyze this"})
        assert metrics.intent == "analyze"
        assert 0.0 <= metrics.output_consistency_score <= 1.0


class TestEngineComparisonFrameworkCompareTest:
    """Tests for EngineComparisonFramework.compare_test()."""

    def test_compare_test_returns_metrics_with_intent_test(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        test_wf = TestWorkflow(exec_tool=mock_exec)
        fw = EngineComparisonFramework(test_workflow=test_wf)
        metrics = fw.compare_test({"task_id": "t1", "prompt": "run tests"})
        assert metrics.intent == "test"

    def test_compare_test_consistency_score_in_range(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        test_wf = TestWorkflow(exec_tool=mock_exec)
        fw = EngineComparisonFramework(test_workflow=test_wf)
        metrics = fw.compare_test({"task_id": "t1", "prompt": "run tests"})
        assert 0.0 <= metrics.output_consistency_score <= 1.0

    def test_compare_test_with_custom_legacy_handler(self):
        mock_exec = _make_mock_exec_tool(ok=True)
        test_wf = TestWorkflow(exec_tool=mock_exec)

        def legacy_handler(task: dict) -> dict:
            return {
                "result": "executed",
                "intent": "test",
                "planName": task.get("planName", ""),
                "status": "ok",
                "executionPath": "legacy",
            }

        fw = EngineComparisonFramework(
            test_workflow=test_wf,
            legacy_test_handler=legacy_handler,
        )
        metrics = fw.compare_test({"task_id": "t1", "prompt": "run tests"})
        assert metrics.intent == "test"
        assert 0.0 <= metrics.output_consistency_score <= 1.0


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Strategies for generating result dicts
_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=20,
)
_value_strategy = st.one_of(
    st.text(min_size=0, max_size=50),
    st.integers(min_value=-100, max_value=100),
    st.booleans(),
    st.none(),
)
_result_dict_strategy = st.dictionaries(
    keys=_key_strategy,
    values=_value_strategy,
    min_size=0,
    max_size=8,
)
_operation_strategy = st.sampled_from(["analyze", "test", "code_change", "deploy"])


class TestPropertyIdenticalResultsConsistency:
    """
    **Property 27: Engine Output Consistency**

    For any two identical results, consistency_score == 1.0.

    **Validates: Requirements 8.4**
    """

    @given(_result_dict_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27_identical_results_have_score_1_0(
        self, result: dict[str, Any], operation: str
    ):
        """
        **Validates: Requirements 8.4**

        For any two identical result dicts, compare() SHALL return
        consistency_score == 1.0.
        """
        fw = EngineComparisonFramework()
        comparison = fw.compare(operation, result, result)
        assert comparison.consistency_score == 1.0

    @given(_result_dict_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27_identical_results_are_consistent(
        self, result: dict[str, Any], operation: str
    ):
        """
        **Validates: Requirements 8.4**

        For any two identical result dicts, compare() SHALL return
        consistent == True.
        """
        fw = EngineComparisonFramework()
        comparison = fw.compare(operation, result, result)
        assert comparison.consistent is True

    @given(_result_dict_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27_identical_results_have_no_discrepancies(
        self, result: dict[str, Any], operation: str
    ):
        """
        **Validates: Requirements 8.4**

        For any two identical result dicts, compare() SHALL return
        an empty discrepancies list.
        """
        fw = EngineComparisonFramework()
        comparison = fw.compare(operation, result, result)
        assert comparison.discrepancies == []


class TestPropertyConsistencyScoreRange:
    """
    **Property 27: Engine Output Consistency**

    consistency_score is always in [0.0, 1.0].

    **Validates: Requirements 8.4**
    """

    @given(_result_dict_strategy, _result_dict_strategy, _operation_strategy)
    @settings(max_examples=150, deadline=None)
    def test_property_27_consistency_score_always_in_0_1(
        self,
        legacy_result: dict[str, Any],
        langgraph_result: dict[str, Any],
        operation: str,
    ):
        """
        **Validates: Requirements 8.4**

        For any two result dicts, compare() SHALL return a consistency_score
        in [0.0, 1.0].
        """
        fw = EngineComparisonFramework()
        comparison = fw.compare(operation, legacy_result, langgraph_result)
        assert 0.0 <= comparison.consistency_score <= 1.0

    @given(_result_dict_strategy, _result_dict_strategy, _operation_strategy)
    @settings(max_examples=150, deadline=None)
    def test_property_27_comparison_result_is_correct_type(
        self,
        legacy_result: dict[str, Any],
        langgraph_result: dict[str, Any],
        operation: str,
    ):
        """
        **Validates: Requirements 8.4**

        compare() SHALL always return a ComparisonResult instance.
        """
        fw = EngineComparisonFramework()
        comparison = fw.compare(operation, legacy_result, langgraph_result)
        assert isinstance(comparison, ComparisonResult)
        assert isinstance(comparison.consistent, bool)
        assert isinstance(comparison.consistency_score, float)
        assert isinstance(comparison.discrepancies, list)

    @given(_result_dict_strategy, _result_dict_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27_consistent_iff_no_discrepancies_and_score_1(
        self,
        legacy_result: dict[str, Any],
        langgraph_result: dict[str, Any],
        operation: str,
    ):
        """
        **Validates: Requirements 8.4**

        consistent == True implies discrepancies is empty.
        """
        fw = EngineComparisonFramework()
        comparison = fw.compare(operation, legacy_result, langgraph_result)
        if comparison.consistent:
            assert comparison.discrepancies == []

