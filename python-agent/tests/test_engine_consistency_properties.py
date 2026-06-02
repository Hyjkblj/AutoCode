"""
Property-based tests for engine output consistency.

Task 22.3: Write property tests for engine consistency
Property 27: Engine Output Consistency
Validates: Requirements 8.4

These tests validate that "WHEN migration is in progress, THE system SHALL
maintain output consistency between engines through comparison testing."
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st, assume

from workflows.comparison_framework import (
    ComparisonMetrics,
    ComparisonMetricsTracker,
    EngineComparisonFramework,
)
from workflows.analyze_workflow import AnalyzeWorkflow
from workflows.code_change_workflow import CodeChangeWorkflow


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for generating arbitrary result dicts (no "error" key → success)
_success_result_strategy = st.dictionaries(
    keys=st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    ),
    values=st.one_of(
        st.text(max_size=50),
        st.integers(),
        st.booleans(),
        st.none(),
    ),
    min_size=0,
    max_size=8,
).filter(lambda d: "error" not in d)

# Strategy for generating failure result dicts (has "error" key)
_failure_result_strategy = st.fixed_dictionaries({"error": st.text(min_size=1, max_size=50)})

# Strategy for any result dict (success or failure)
_any_result_strategy = st.one_of(_success_result_strategy, _failure_result_strategy)

# Strategy for operation names
_operation_strategy = st.sampled_from(["analyze", "test", "code_change"])

# Strategy for task IDs
_task_id_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
)

# Strategy for prompt strings
_prompt_strategy = st.text(min_size=0, max_size=200)

# Strategy for a single ComparisonMetrics record
def _make_metrics(
    langgraph_success: bool,
    legacy_success: bool,
    consistency_score: float = 1.0,
) -> ComparisonMetrics:
    return ComparisonMetrics(
        intent="analyze",
        legacy_success=legacy_success,
        langgraph_success=langgraph_success,
        success_rate=(int(legacy_success) + int(langgraph_success)) / 2.0,
        output_consistency_score=consistency_score,
    )


# ---------------------------------------------------------------------------
# Property 27a: Identical outputs are always consistent
# ---------------------------------------------------------------------------

class TestProperty27aIdenticalOutputsConsistent:
    """
    **Property 27a: Identical outputs are always consistent**

    For any result dict, compare(op, result, result) SHALL produce
    consistency_score == 1.0 and consistent == True.

    **Validates: Requirements 8.4**
    """

    @given(_any_result_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27a_identical_results_score_is_one(
        self, result: dict[str, Any], operation: str
    ) -> None:
        """
        **Property 27a: For any result dict, comparing it with itself SHALL
        yield consistency_score == 1.0.**

        **Validates: Requirements 8.4**
        """
        framework = EngineComparisonFramework()
        comparison = framework.compare(operation, result, result)

        assert comparison.consistency_score == 1.0, (
            f"Identical results must have consistency_score=1.0, "
            f"got {comparison.consistency_score} for result={result!r}"
        )

    @given(_any_result_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27a_identical_results_are_consistent(
        self, result: dict[str, Any], operation: str
    ) -> None:
        """
        **Property 27a: For any result dict, comparing it with itself SHALL
        yield consistent == True.**

        **Validates: Requirements 8.4**
        """
        framework = EngineComparisonFramework()
        comparison = framework.compare(operation, result, result)

        assert comparison.consistent is True, (
            f"Identical results must be consistent, "
            f"got consistent={comparison.consistent} for result={result!r}"
        )

    @given(_any_result_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27a_identical_results_have_no_discrepancies(
        self, result: dict[str, Any], operation: str
    ) -> None:
        """
        **Property 27a: For any result dict, comparing it with itself SHALL
        yield an empty discrepancies list.**

        **Validates: Requirements 8.4**
        """
        framework = EngineComparisonFramework()
        comparison = framework.compare(operation, result, result)

        assert comparison.discrepancies == [], (
            f"Identical results must have no discrepancies, "
            f"got {comparison.discrepancies!r} for result={result!r}"
        )


# ---------------------------------------------------------------------------
# Property 27b: Consistency score is always in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestProperty27bConsistencyScoreRange:
    """
    **Property 27b: Consistency score is always in [0.0, 1.0]**

    For any two result dicts, compare(op, r1, r2) SHALL produce a
    consistency_score in [0.0, 1.0].

    **Validates: Requirements 8.4**
    """

    @given(_any_result_strategy, _any_result_strategy, _operation_strategy)
    @settings(max_examples=200, deadline=None)
    def test_property_27b_score_in_unit_interval(
        self,
        r1: dict[str, Any],
        r2: dict[str, Any],
        operation: str,
    ) -> None:
        """
        **Property 27b: For any two result dicts, the consistency_score SHALL
        be in [0.0, 1.0].**

        **Validates: Requirements 8.4**
        """
        framework = EngineComparisonFramework()
        comparison = framework.compare(operation, r1, r2)

        assert 0.0 <= comparison.consistency_score <= 1.0, (
            f"consistency_score={comparison.consistency_score} is outside [0.0, 1.0] "
            f"for r1={r1!r}, r2={r2!r}"
        )

    @given(_any_result_strategy, _any_result_strategy, _operation_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_27b_score_is_float(
        self,
        r1: dict[str, Any],
        r2: dict[str, Any],
        operation: str,
    ) -> None:
        """
        **Property 27b: The consistency_score SHALL be a float.**

        **Validates: Requirements 8.4**
        """
        framework = EngineComparisonFramework()
        comparison = framework.compare(operation, r1, r2)

        assert isinstance(comparison.consistency_score, float), (
            f"consistency_score must be float, got {type(comparison.consistency_score)}"
        )


# ---------------------------------------------------------------------------
# Property 27c: Consistency is symmetric
# ---------------------------------------------------------------------------

class TestProperty27cConsistencySymmetry:
    """
    **Property 27c: Consistency is symmetric**

    For any two result dicts, compare(op, r1, r2).consistency_score SHALL
    equal compare(op, r2, r1).consistency_score.

    **Validates: Requirements 8.4**
    """

    @given(_any_result_strategy, _any_result_strategy, _operation_strategy)
    @settings(max_examples=200, deadline=None)
    def test_property_27c_score_is_symmetric(
        self,
        r1: dict[str, Any],
        r2: dict[str, Any],
        operation: str,
    ) -> None:
        """
        **Property 27c: For any two result dicts, compare(op, r1, r2).consistency_score
        SHALL equal compare(op, r2, r1).consistency_score.**

        **Validates: Requirements 8.4**
        """
        framework = EngineComparisonFramework()
        forward = framework.compare(operation, r1, r2)
        backward = framework.compare(operation, r2, r1)

        assert forward.consistency_score == backward.consistency_score, (
            f"Consistency score is not symmetric: "
            f"compare(r1,r2)={forward.consistency_score} != "
            f"compare(r2,r1)={backward.consistency_score} "
            f"for r1={r1!r}, r2={r2!r}"
        )


# ---------------------------------------------------------------------------
# Property 27d: ComparisonMetricsTracker rollback threshold invariant
# ---------------------------------------------------------------------------

class TestProperty27dRollbackThresholdInvariant:
    """
    **Property 27d: ComparisonMetricsTracker rollback threshold invariant**

    For any sequence of metrics where all langgraph_success=True,
    should_rollback() SHALL always be False.

    **Validates: Requirements 8.4**
    """

    @given(
        st.lists(
            st.booleans(),  # legacy_success values
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_27d_no_rollback_when_langgraph_always_succeeds(
        self, legacy_successes: list[bool]
    ) -> None:
        """
        **Property 27d: For any sequence of metrics where all
        langgraph_success=True, should_rollback() SHALL be False.**

        **Validates: Requirements 8.4**
        """
        tracker = ComparisonMetricsTracker()

        for legacy_success in legacy_successes:
            metrics = _make_metrics(langgraph_success=True, legacy_success=legacy_success)
            tracker.record(metrics)

        assert tracker.should_rollback() is False, (
            f"should_rollback() must be False when all langgraph_success=True, "
            f"got True for legacy_successes={legacy_successes}"
        )

    @given(
        st.lists(
            st.booleans(),  # legacy_success values
            min_size=1,
            max_size=50,
        ),
        st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_27d_no_rollback_when_langgraph_always_succeeds_any_threshold(
        self, legacy_successes: list[bool], threshold: float
    ) -> None:
        """
        **Property 27d: For any sequence of metrics where all
        langgraph_success=True, should_rollback(threshold) SHALL be False
        for any threshold in [0.0, 1.0].**

        **Validates: Requirements 8.4**
        """
        tracker = ComparisonMetricsTracker()

        for legacy_success in legacy_successes:
            metrics = _make_metrics(langgraph_success=True, legacy_success=legacy_success)
            tracker.record(metrics)

        assert tracker.should_rollback(threshold=threshold) is False, (
            f"should_rollback(threshold={threshold}) must be False when all "
            f"langgraph_success=True"
        )


# ---------------------------------------------------------------------------
# Property 27e: Rollback is triggered when gap exceeds threshold
# ---------------------------------------------------------------------------

class TestProperty27eRollbackTriggeredOnGap:
    """
    **Property 27e: Rollback is triggered when gap exceeds threshold**

    For any sequence where legacy always succeeds and langgraph always fails,
    should_rollback() SHALL be True.

    **Validates: Requirements 8.4**
    """

    @given(
        st.integers(min_value=1, max_value=50),  # number of records
    )
    @settings(max_examples=100, deadline=None)
    def test_property_27e_rollback_when_legacy_succeeds_langgraph_fails(
        self, n: int
    ) -> None:
        """
        **Property 27e: For any non-empty sequence where legacy always succeeds
        and langgraph always fails, should_rollback() SHALL be True.**

        **Validates: Requirements 8.4**
        """
        tracker = ComparisonMetricsTracker()

        for _ in range(n):
            metrics = _make_metrics(langgraph_success=False, legacy_success=True)
            tracker.record(metrics)

        assert tracker.should_rollback() is True, (
            f"should_rollback() must be True when legacy always succeeds and "
            f"langgraph always fails (n={n})"
        )

    @given(
        st.integers(min_value=1, max_value=50),
        st.floats(min_value=0.0, max_value=0.5, exclude_max=True),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_27e_rollback_with_small_threshold(
        self, n: int, threshold: float
    ) -> None:
        """
        **Property 27e: For any sequence where legacy always succeeds and
        langgraph always fails, should_rollback(threshold) SHALL be True
        for any threshold < 1.0.**

        **Validates: Requirements 8.4**
        """
        tracker = ComparisonMetricsTracker()

        for _ in range(n):
            metrics = _make_metrics(langgraph_success=False, legacy_success=True)
            tracker.record(metrics)

        # Gap is 1.0 (legacy_rate=1.0, langgraph_rate=0.0), so any threshold < 1.0
        # should trigger rollback
        assert tracker.should_rollback(threshold=threshold) is True, (
            f"should_rollback(threshold={threshold}) must be True when gap=1.0"
        )

    def test_property_27e_empty_tracker_never_rolls_back(self) -> None:
        """
        **Property 27e: An empty tracker SHALL never recommend rollback.**

        **Validates: Requirements 8.4**
        """
        tracker = ComparisonMetricsTracker()
        assert tracker.should_rollback() is False


# ---------------------------------------------------------------------------
# Property 27f: AnalyzeWorkflow always returns intent="analyze"
# ---------------------------------------------------------------------------

class TestProperty27fAnalyzeWorkflowIntent:
    """
    **Property 27f: AnalyzeWorkflow always returns intent="analyze"**

    For any task_id and prompt, AnalyzeWorkflow.run() SHALL return a state
    with metadata["analyze_result"]["intent"] == "analyze".

    **Validates: Requirements 8.4**
    """

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_27f_analyze_workflow_intent_is_always_analyze(
        self, task_id: str, prompt: str
    ) -> None:
        """
        **Property 27f: For any task_id and prompt, AnalyzeWorkflow.run()
        SHALL return state with metadata["analyze_result"]["intent"] == "analyze".**

        **Validates: Requirements 8.4**
        """
        # Use a mock LLM client to avoid real LLM calls
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "1. Step one\n2. Step two"

        workflow = AnalyzeWorkflow(llm_client=mock_llm)
        task = {"task_id": task_id, "prompt": prompt}
        final_state = workflow.run(task)

        metadata = final_state.get("metadata") or {}
        analyze_result = metadata.get("analyze_result") or {}

        assert analyze_result.get("intent") == "analyze", (
            f"AnalyzeWorkflow must always produce intent='analyze', "
            f"got intent={analyze_result.get('intent')!r} "
            f"for task_id={task_id!r}, prompt={prompt!r}"
        )

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_27f_analyze_workflow_result_key_is_planned(
        self, task_id: str, prompt: str
    ) -> None:
        """
        **Property 27f: For any task_id and prompt, AnalyzeWorkflow.run()
        SHALL return state with metadata["analyze_result"]["result"] == "planned".**

        **Validates: Requirements 8.4**
        """
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Analysis complete"

        workflow = AnalyzeWorkflow(llm_client=mock_llm)
        task = {"task_id": task_id, "prompt": prompt}
        final_state = workflow.run(task)

        metadata = final_state.get("metadata") or {}
        analyze_result = metadata.get("analyze_result") or {}

        assert analyze_result.get("result") == "planned", (
            f"AnalyzeWorkflow must always produce result='planned', "
            f"got result={analyze_result.get('result')!r}"
        )

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_27f_analyze_workflow_execution_path_is_langgraph(
        self, task_id: str, prompt: str
    ) -> None:
        """
        **Property 27f: For any task_id and prompt, AnalyzeWorkflow.run()
        SHALL return state with metadata["analyze_result"]["executionPath"] == "langgraph".**

        **Validates: Requirements 8.4**
        """
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Analysis complete"

        workflow = AnalyzeWorkflow(llm_client=mock_llm)
        task = {"task_id": task_id, "prompt": prompt}
        final_state = workflow.run(task)

        metadata = final_state.get("metadata") or {}
        analyze_result = metadata.get("analyze_result") or {}

        assert analyze_result.get("executionPath") == "langgraph", (
            f"AnalyzeWorkflow must always produce executionPath='langgraph', "
            f"got executionPath={analyze_result.get('executionPath')!r}"
        )


# ---------------------------------------------------------------------------
# Property 27g: CodeChangeWorkflow always returns intent="code_change"
# ---------------------------------------------------------------------------

class TestProperty27gCodeChangeWorkflowIntent:
    """
    **Property 27g: CodeChangeWorkflow always returns intent="code_change"**

    For any task_id and prompt, CodeChangeWorkflow.run() SHALL return a state
    with metadata["code_change_result"]["intent"] == "code_change".

    **Validates: Requirements 8.4**
    """

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_27g_code_change_workflow_intent_is_always_code_change(
        self, task_id: str, prompt: str
    ) -> None:
        """
        **Property 27g: For any task_id and prompt, CodeChangeWorkflow.run()
        SHALL return state with metadata["code_change_result"]["intent"] == "code_change".**

        **Validates: Requirements 8.4**
        """
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "1. Change file A\n2. Update function B"

        workflow = CodeChangeWorkflow(llm_client=mock_llm)
        task = {"task_id": task_id, "prompt": prompt}
        final_state = workflow.run(task)

        metadata = final_state.get("metadata") or {}
        code_change_result = metadata.get("code_change_result") or {}

        assert code_change_result.get("intent") == "code_change", (
            f"CodeChangeWorkflow must always produce intent='code_change', "
            f"got intent={code_change_result.get('intent')!r} "
            f"for task_id={task_id!r}, prompt={prompt!r}"
        )

    @given(_task_id_strategy, _prompt_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_27g_code_change_workflow_execution_path_is_langgraph(
        self, task_id: str, prompt: str
    ) -> None:
        """
        **Property 27g: For any task_id and prompt, CodeChangeWorkflow.run()
        SHALL return state with metadata["code_change_result"]["executionPath"] == "langgraph".**

        **Validates: Requirements 8.4**
        """
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "1. Change file A\n2. Update function B"

        workflow = CodeChangeWorkflow(llm_client=mock_llm)
        task = {"task_id": task_id, "prompt": prompt}
        final_state = workflow.run(task)

        metadata = final_state.get("metadata") or {}
        code_change_result = metadata.get("code_change_result") or {}

        assert code_change_result.get("executionPath") == "langgraph", (
            f"CodeChangeWorkflow must always produce executionPath='langgraph', "
            f"got executionPath={code_change_result.get('executionPath')!r}"
        )

    @given(
        _task_id_strategy,
        st.text(min_size=1, max_size=200),  # non-empty prompt ensures LLM is called
    )
    @settings(max_examples=50, deadline=None)
    def test_property_27g_code_change_workflow_result_field_is_valid(
        self, task_id: str, prompt: str
    ) -> None:
        """
        **Property 27g: For any task_id and non-empty prompt, CodeChangeWorkflow.run()
        SHALL return state with metadata["code_change_result"]["result"] in
        {"applied", "failed"}.**

        **Validates: Requirements 8.4**
        """
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "1. Change file A\n2. Update function B"

        workflow = CodeChangeWorkflow(llm_client=mock_llm)
        task = {"task_id": task_id, "prompt": prompt}
        final_state = workflow.run(task)

        metadata = final_state.get("metadata") or {}
        code_change_result = metadata.get("code_change_result") or {}
        result_value = code_change_result.get("result")

        assert result_value in ("applied", "failed"), (
            f"CodeChangeWorkflow result must be 'applied' or 'failed', "
            f"got result={result_value!r}"
        )
