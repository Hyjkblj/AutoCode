"""
Extended tests for EngineComparisonFramework.compare_code_change() and
ComparisonMetricsTracker.

Task 22.2: Implement dual-engine comparison testing

Tests cover:
- compare_code_change(): returns ComparisonMetrics with intent="code_change"
- compare_code_change(): consistency score in [0.0, 1.0]
- compare_code_change(): custom legacy handler is used
- ComparisonMetricsTracker.record() and get_summary() aggregate correctly
- ComparisonMetricsTracker.should_rollback() with various success rate scenarios
- Property test: should_rollback() returns True when LangGraph success rate is
  significantly lower than legacy success rate
- Property test: avg_consistency_score is always in [0.0, 1.0]

**Validates: Requirements 8.4, 8.7**
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from workflows.code_change_workflow import CodeChangeWorkflow
from workflows.comparison_framework import (
    ComparisonMetrics,
    ComparisonMetricsTracker,
    EngineComparisonFramework,
    _CODE_CHANGE_CONSISTENCY_KEYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(response: str = "mock code change") -> MagicMock:
    """Return a mock LLMClient whose generate() returns *response*."""
    mock = MagicMock()
    mock.generate.return_value = response
    return mock


def _make_failing_llm() -> MagicMock:
    """Return a mock LLMClient whose generate() always raises."""
    mock = MagicMock()
    mock.generate.side_effect = RuntimeError("LLM unavailable")
    return mock


def _make_metrics(
    *,
    legacy_success: bool = True,
    langgraph_success: bool = True,
    consistency_score: float = 1.0,
    intent: str = "code_change",
) -> ComparisonMetrics:
    """Build a :class:`ComparisonMetrics` instance for testing."""
    successes = sum([legacy_success, langgraph_success])
    return ComparisonMetrics(
        intent=intent,
        legacy_success=legacy_success,
        langgraph_success=langgraph_success,
        success_rate=successes / 2.0,
        output_consistency_score=consistency_score,
        latency_comparison={"legacy_seconds": 0.1, "langgraph_seconds": 0.1, "speedup": 1.0},
        discrepancies=[],
    )


def _make_legacy_code_change_handler(success: bool = True) -> Any:
    """Return a legacy code_change handler that always succeeds or fails."""
    def handler(task: dict) -> dict:
        if not success:
            raise RuntimeError("legacy engine failed")
        return {
            "result": "applied",
            "intent": "code_change",
            "success": True,
            "planName": task.get("planName", ""),
            "change_type": "general_change",
            "changes": [],
            "executionPath": "legacy",
        }
    return handler


# ---------------------------------------------------------------------------
# Tests for _CODE_CHANGE_CONSISTENCY_KEYS
# ---------------------------------------------------------------------------

class TestCodeChangeConsistencyKeys:
    """Tests for the _CODE_CHANGE_CONSISTENCY_KEYS constant."""

    def test_consistency_keys_is_tuple(self):
        assert isinstance(_CODE_CHANGE_CONSISTENCY_KEYS, tuple)

    def test_consistency_keys_contains_result(self):
        assert "result" in _CODE_CHANGE_CONSISTENCY_KEYS

    def test_consistency_keys_contains_intent(self):
        assert "intent" in _CODE_CHANGE_CONSISTENCY_KEYS

    def test_consistency_keys_contains_success(self):
        assert "success" in _CODE_CHANGE_CONSISTENCY_KEYS

    def test_consistency_keys_contains_execution_path(self):
        assert "executionPath" in _CODE_CHANGE_CONSISTENCY_KEYS

    def test_consistency_keys_is_non_empty(self):
        assert len(_CODE_CHANGE_CONSISTENCY_KEYS) > 0


# ---------------------------------------------------------------------------
# Tests for EngineComparisonFramework.compare_code_change()
# ---------------------------------------------------------------------------

class TestCompareCodeChange:
    """Tests for EngineComparisonFramework.compare_code_change()."""

    def test_compare_code_change_returns_metrics_with_intent_code_change(self):
        mock_llm = _make_mock_llm("def new_func(): pass")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add a function"})
        assert metrics.intent == "code_change"

    def test_compare_code_change_returns_comparison_metrics_instance(self):
        mock_llm = _make_mock_llm("def new_func(): pass")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add a function"})
        assert isinstance(metrics, ComparisonMetrics)

    def test_compare_code_change_consistency_score_in_range(self):
        mock_llm = _make_mock_llm("def new_func(): pass")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add a function"})
        assert 0.0 <= metrics.output_consistency_score <= 1.0

    def test_compare_code_change_has_latency_comparison(self):
        mock_llm = _make_mock_llm("code")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "fix bug"})
        assert "legacy_seconds" in metrics.latency_comparison
        assert "langgraph_seconds" in metrics.latency_comparison
        assert "speedup" in metrics.latency_comparison

    def test_compare_code_change_uses_custom_legacy_handler(self):
        """Custom legacy handler result is used in comparison."""
        mock_llm = _make_mock_llm("code")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)

        call_log: list[dict] = []

        def custom_handler(task: dict) -> dict:
            call_log.append(task)
            return {
                "result": "applied",
                "intent": "code_change",
                "success": True,
                "planName": "custom_plan",
                "change_type": "addition",
                "changes": [],
                "executionPath": "legacy",
            }

        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=custom_handler,
        )
        fw.compare_code_change({"task_id": "t1", "prompt": "add feature"})
        assert len(call_log) == 1

    def test_compare_code_change_uses_default_legacy_stub_when_no_handler(self):
        """When no legacy handler is provided, the default stub is used."""
        mock_llm = _make_mock_llm("code")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(code_change_workflow=code_change_wf)
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add feature"})
        assert metrics.intent == "code_change"
        assert 0.0 <= metrics.output_consistency_score <= 1.0

    def test_compare_code_change_legacy_failure_recorded_in_metrics(self):
        """When legacy handler raises, legacy_success is False."""
        mock_llm = _make_mock_llm("code")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(success=False),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add feature"})
        assert metrics.legacy_success is False

    def test_compare_code_change_langgraph_failure_recorded_in_metrics(self):
        """When LangGraph LLM always fails, langgraph_success is False."""
        code_change_wf = CodeChangeWorkflow(
            llm_client=_make_failing_llm(),
            max_retries=0,
        )
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add feature"})
        assert metrics.langgraph_success is False

    def test_compare_code_change_discrepancies_is_list(self):
        mock_llm = _make_mock_llm("code")
        code_change_wf = CodeChangeWorkflow(llm_client=mock_llm)
        fw = EngineComparisonFramework(
            code_change_workflow=code_change_wf,
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        metrics = fw.compare_code_change({"task_id": "t1", "prompt": "add feature"})
        assert isinstance(metrics.discrepancies, list)

    def test_compare_code_change_lazy_creates_code_change_workflow(self):
        """compare_code_change() creates a CodeChangeWorkflow lazily when none provided."""
        fw = EngineComparisonFramework(
            legacy_code_change_handler=_make_legacy_code_change_handler(),
        )
        # Accessing the property should create a workflow
        wf = fw.code_change_workflow
        assert isinstance(wf, CodeChangeWorkflow)


# ---------------------------------------------------------------------------
# Tests for ComparisonMetricsTracker.record() and get_summary()
# ---------------------------------------------------------------------------

class TestComparisonMetricsTrackerRecord:
    """Tests for ComparisonMetricsTracker.record() and get_summary()."""

    def test_empty_tracker_summary_has_zero_total(self):
        tracker = ComparisonMetricsTracker()
        summary = tracker.get_summary()
        assert summary["total_comparisons"] == 0

    def test_empty_tracker_summary_has_zero_rates(self):
        tracker = ComparisonMetricsTracker()
        summary = tracker.get_summary()
        assert summary["legacy_success_rate"] == 0.0
        assert summary["langgraph_success_rate"] == 0.0
        assert summary["avg_consistency_score"] == 0.0

    def test_empty_tracker_rollback_not_recommended(self):
        tracker = ComparisonMetricsTracker()
        summary = tracker.get_summary()
        assert summary["rollback_recommended"] is False

    def test_record_increments_total_comparisons(self):
        tracker = ComparisonMetricsTracker()
        tracker.record(_make_metrics())
        assert tracker.get_summary()["total_comparisons"] == 1

    def test_record_multiple_increments_total(self):
        tracker = ComparisonMetricsTracker()
        for _ in range(5):
            tracker.record(_make_metrics())
        assert tracker.get_summary()["total_comparisons"] == 5

    def test_all_successes_gives_rate_1_0(self):
        tracker = ComparisonMetricsTracker()
        for _ in range(4):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        summary = tracker.get_summary()
        assert summary["legacy_success_rate"] == 1.0
        assert summary["langgraph_success_rate"] == 1.0

    def test_all_failures_gives_rate_0_0(self):
        tracker = ComparisonMetricsTracker()
        for _ in range(3):
            tracker.record(_make_metrics(legacy_success=False, langgraph_success=False))
        summary = tracker.get_summary()
        assert summary["legacy_success_rate"] == 0.0
        assert summary["langgraph_success_rate"] == 0.0

    def test_mixed_successes_gives_correct_rate(self):
        tracker = ComparisonMetricsTracker()
        # 3 legacy successes out of 4
        tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        tracker.record(_make_metrics(legacy_success=False, langgraph_success=False))
        summary = tracker.get_summary()
        assert summary["legacy_success_rate"] == pytest.approx(0.75)
        assert summary["langgraph_success_rate"] == pytest.approx(0.5)

    def test_avg_consistency_score_is_mean_of_records(self):
        tracker = ComparisonMetricsTracker()
        tracker.record(_make_metrics(consistency_score=0.8))
        tracker.record(_make_metrics(consistency_score=0.6))
        summary = tracker.get_summary()
        assert summary["avg_consistency_score"] == pytest.approx(0.7)

    def test_avg_consistency_score_is_in_0_1_range(self):
        tracker = ComparisonMetricsTracker()
        tracker.record(_make_metrics(consistency_score=1.0))
        tracker.record(_make_metrics(consistency_score=0.0))
        summary = tracker.get_summary()
        assert 0.0 <= summary["avg_consistency_score"] <= 1.0

    def test_summary_contains_all_required_keys(self):
        tracker = ComparisonMetricsTracker()
        tracker.record(_make_metrics())
        summary = tracker.get_summary()
        required_keys = {
            "total_comparisons",
            "legacy_success_rate",
            "langgraph_success_rate",
            "avg_consistency_score",
            "rollback_recommended",
        }
        assert required_keys.issubset(summary.keys())

    def test_rollback_recommended_in_summary_matches_should_rollback(self):
        tracker = ComparisonMetricsTracker()
        # Legacy always succeeds, LangGraph always fails → rollback
        for _ in range(5):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        summary = tracker.get_summary()
        assert summary["rollback_recommended"] == tracker.should_rollback()


# ---------------------------------------------------------------------------
# Tests for ComparisonMetricsTracker.should_rollback()
# ---------------------------------------------------------------------------

class TestComparisonMetricsTrackerShouldRollback:
    """Tests for ComparisonMetricsTracker.should_rollback()."""

    def test_empty_tracker_should_not_rollback(self):
        tracker = ComparisonMetricsTracker()
        assert tracker.should_rollback() is False

    def test_both_engines_succeed_no_rollback(self):
        tracker = ComparisonMetricsTracker()
        for _ in range(10):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        assert tracker.should_rollback() is False

    def test_both_engines_fail_no_rollback(self):
        """When both fail equally, no rollback is needed."""
        tracker = ComparisonMetricsTracker()
        for _ in range(10):
            tracker.record(_make_metrics(legacy_success=False, langgraph_success=False))
        assert tracker.should_rollback() is False

    def test_langgraph_significantly_worse_triggers_rollback(self):
        """Legacy 100% success, LangGraph 0% success → rollback."""
        tracker = ComparisonMetricsTracker()
        for _ in range(10):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        assert tracker.should_rollback() is True

    def test_langgraph_slightly_worse_within_threshold_no_rollback(self):
        """Legacy 100%, LangGraph 95% → gap 0.05 < threshold 0.1 → no rollback."""
        tracker = ComparisonMetricsTracker()
        # 20 records: 19 langgraph successes, 1 failure → 95% success rate
        for _ in range(19):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        assert tracker.should_rollback(threshold=0.1) is False

    def test_langgraph_worse_beyond_threshold_triggers_rollback(self):
        """Legacy 100%, LangGraph 80% → gap 0.20 > threshold 0.1 → rollback."""
        tracker = ComparisonMetricsTracker()
        # 10 records: 8 langgraph successes, 2 failures → 80% success rate
        for _ in range(8):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        for _ in range(2):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        assert tracker.should_rollback(threshold=0.1) is True

    def test_custom_threshold_respected(self):
        """With threshold=0.3, a 20% gap should NOT trigger rollback."""
        tracker = ComparisonMetricsTracker()
        for _ in range(8):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        for _ in range(2):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        # gap = 0.20, threshold = 0.30 → no rollback
        assert tracker.should_rollback(threshold=0.3) is False

    def test_langgraph_better_than_legacy_no_rollback(self):
        """When LangGraph outperforms legacy, no rollback."""
        tracker = ComparisonMetricsTracker()
        for _ in range(5):
            tracker.record(_make_metrics(legacy_success=False, langgraph_success=True))
        assert tracker.should_rollback() is False

    def test_equal_success_rates_no_rollback(self):
        """When success rates are equal, no rollback."""
        tracker = ComparisonMetricsTracker()
        for _ in range(5):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        for _ in range(5):
            tracker.record(_make_metrics(legacy_success=False, langgraph_success=False))
        assert tracker.should_rollback() is False

    def test_exactly_at_threshold_no_rollback(self):
        """Gap exactly equal to threshold should NOT trigger rollback (strict >)."""
        tracker = ComparisonMetricsTracker()
        # 10 records: legacy 100%, langgraph 90% → gap = 0.10
        for _ in range(9):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))
        tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))
        # gap == threshold → should NOT rollback (strictly greater than)
        assert tracker.should_rollback(threshold=0.1) is False


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Strategies
_bool_strategy = st.booleans()
_score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_metrics_list_strategy = st.lists(
    st.builds(
        _make_metrics,
        legacy_success=_bool_strategy,
        langgraph_success=_bool_strategy,
        consistency_score=_score_strategy,
    ),
    min_size=1,
    max_size=50,
)
_threshold_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


class TestPropertyShouldRollback:
    """
    **Property: Automated Rollback on Performance Degradation**

    should_rollback() returns True when LangGraph success rate is
    significantly lower than legacy success rate.

    **Validates: Requirements 8.7**
    """

    @given(
        st.integers(min_value=1, max_value=50),
        st.integers(min_value=0, max_value=50),
        _threshold_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_property_rollback_when_langgraph_significantly_worse(
        self,
        legacy_only_successes: int,
        both_successes: int,
        threshold: float,
    ):
        """
        **Validates: Requirements 8.7**

        When legacy_success_rate - langgraph_success_rate > threshold,
        should_rollback() SHALL return True.
        """
        tracker = ComparisonMetricsTracker()

        # Records where only legacy succeeds
        for _ in range(legacy_only_successes):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=False))

        # Records where both succeed
        for _ in range(both_successes):
            tracker.record(_make_metrics(legacy_success=True, langgraph_success=True))

        total = legacy_only_successes + both_successes
        if total == 0:
            return  # skip degenerate case

        legacy_rate = 1.0  # all legacy records succeed
        langgraph_rate = both_successes / total
        gap = legacy_rate - langgraph_rate

        result = tracker.should_rollback(threshold=threshold)

        if gap > threshold:
            assert result is True, (
                f"Expected rollback: legacy_rate={legacy_rate:.3f}, "
                f"langgraph_rate={langgraph_rate:.3f}, gap={gap:.3f}, "
                f"threshold={threshold:.3f}"
            )
        else:
            assert result is False, (
                f"Expected no rollback: legacy_rate={legacy_rate:.3f}, "
                f"langgraph_rate={langgraph_rate:.3f}, gap={gap:.3f}, "
                f"threshold={threshold:.3f}"
            )


class TestPropertyAvgConsistencyScore:
    """
    **Property: Consistency Score Range**

    avg_consistency_score in get_summary() is always in [0.0, 1.0].

    **Validates: Requirements 8.4**
    """

    @given(_metrics_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_avg_consistency_score_always_in_0_1(
        self, metrics_list: list[ComparisonMetrics]
    ):
        """
        **Validates: Requirements 8.4**

        For any sequence of recorded ComparisonMetrics, the
        avg_consistency_score in get_summary() SHALL be in [0.0, 1.0].
        """
        tracker = ComparisonMetricsTracker()
        for m in metrics_list:
            tracker.record(m)
        summary = tracker.get_summary()
        assert 0.0 <= summary["avg_consistency_score"] <= 1.0

    @given(_metrics_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_success_rates_always_in_0_1(
        self, metrics_list: list[ComparisonMetrics]
    ):
        """
        **Validates: Requirements 8.4, 8.7**

        For any sequence of recorded ComparisonMetrics, both
        legacy_success_rate and langgraph_success_rate SHALL be in [0.0, 1.0].
        """
        tracker = ComparisonMetricsTracker()
        for m in metrics_list:
            tracker.record(m)
        summary = tracker.get_summary()
        assert 0.0 <= summary["legacy_success_rate"] <= 1.0
        assert 0.0 <= summary["langgraph_success_rate"] <= 1.0

    @given(_metrics_list_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_total_comparisons_matches_records_count(
        self, metrics_list: list[ComparisonMetrics]
    ):
        """
        **Validates: Requirements 8.4**

        total_comparisons in get_summary() SHALL equal the number of
        records added via record().
        """
        tracker = ComparisonMetricsTracker()
        for m in metrics_list:
            tracker.record(m)
        summary = tracker.get_summary()
        assert summary["total_comparisons"] == len(metrics_list)

    @given(_metrics_list_strategy, _threshold_strategy)
    @settings(max_examples=100, deadline=None)
    def test_property_rollback_recommended_consistent_with_should_rollback(
        self, metrics_list: list[ComparisonMetrics], threshold: float
    ):
        """
        **Validates: Requirements 8.7**

        rollback_recommended in get_summary() (using default threshold)
        SHALL equal should_rollback() with the default threshold.
        """
        tracker = ComparisonMetricsTracker()
        for m in metrics_list:
            tracker.record(m)
        summary = tracker.get_summary()
        # summary uses default threshold (0.1)
        assert summary["rollback_recommended"] == tracker.should_rollback(threshold=0.1)
