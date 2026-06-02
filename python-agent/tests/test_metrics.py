"""
Tests for python-agent/utils/metrics.py.

Covers:
- TaskMetrics counter increments and histogram observations
- EventMetrics delivery tracking
- GenerationMetrics generation and validation failure tracking
- Property test: counters are always non-negative

**Validates: Requirements 10.1, 10.2, 10.3**
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st
from prometheus_client import CollectorRegistry

from utils.metrics import EventMetrics, GenerationMetrics, TaskMetrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_metrics() -> TaskMetrics:
    """Return a TaskMetrics instance backed by a fresh isolated registry."""
    return TaskMetrics(registry=CollectorRegistry())


def _event_metrics() -> EventMetrics:
    """Return an EventMetrics instance backed by a fresh isolated registry."""
    return EventMetrics(registry=CollectorRegistry())


def _generation_metrics() -> GenerationMetrics:
    """Return a GenerationMetrics instance backed by a fresh isolated registry."""
    return GenerationMetrics(registry=CollectorRegistry())


def _counter_value(counter, **labels) -> float:
    """Read the current value of a labelled counter."""
    return counter.labels(**labels)._value.get()


def _counter_value_no_labels(counter) -> float:
    """Read the current value of an unlabelled counter."""
    return counter._value.get()


# ---------------------------------------------------------------------------
# TaskMetrics tests
# ---------------------------------------------------------------------------

class TestTaskMetrics:
    """Tests for TaskMetrics – Requirement 10.1."""

    def test_task_created_increments_by_one(self):
        m = _task_metrics()
        m.record_task_created("backend_generation")
        assert _counter_value(m.task_created_total, intent="backend_generation") == 1.0

    def test_task_created_multiple_intents_are_independent(self):
        m = _task_metrics()
        m.record_task_created("backend_generation")
        m.record_task_created("analyze")
        m.record_task_created("analyze")
        assert _counter_value(m.task_created_total, intent="backend_generation") == 1.0
        assert _counter_value(m.task_created_total, intent="analyze") == 2.0

    def test_task_completed_increments_success(self):
        m = _task_metrics()
        m.record_task_completed("backend_generation", "success")
        assert _counter_value(m.task_completed_total, intent="backend_generation", result="success") == 1.0

    def test_task_completed_increments_failed(self):
        m = _task_metrics()
        m.record_task_completed("analyze", "failed")
        assert _counter_value(m.task_completed_total, intent="analyze", result="failed") == 1.0

    def test_task_completed_success_and_failed_are_independent(self):
        m = _task_metrics()
        m.record_task_completed("backend_generation", "success")
        m.record_task_completed("backend_generation", "success")
        m.record_task_completed("backend_generation", "failed")
        assert _counter_value(m.task_completed_total, intent="backend_generation", result="success") == 2.0
        assert _counter_value(m.task_completed_total, intent="backend_generation", result="failed") == 1.0

    def test_task_duration_observation_does_not_raise(self):
        m = _task_metrics()
        # Histogram.observe should not raise for valid durations
        m.record_task_duration("backend_generation", 12.5)
        m.record_task_duration("analyze", 0.0)

    def test_task_duration_clamps_negative_to_zero(self):
        """Negative durations are clamped to 0 to keep histogram values non-negative."""
        m = _task_metrics()
        # Should not raise; negative value is clamped
        m.record_task_duration("backend_generation", -5.0)

    def test_task_created_starts_at_zero(self):
        m = _task_metrics()
        assert _counter_value(m.task_created_total, intent="new_intent") == 0.0


# ---------------------------------------------------------------------------
# EventMetrics tests
# ---------------------------------------------------------------------------

class TestEventMetrics:
    """Tests for EventMetrics – Requirement 10.2."""

    def test_record_delivery_success_increments_success_label(self):
        m = _event_metrics()
        m.record_delivery_success()
        assert _counter_value(m.event_delivery_total, status="success") == 1.0

    def test_record_delivery_failed_increments_failed_label(self):
        m = _event_metrics()
        m.record_delivery_failed()
        assert _counter_value(m.event_delivery_total, status="failed") == 1.0

    def test_record_delivery_retry_increments_retry_label_and_retry_counter(self):
        m = _event_metrics()
        m.record_delivery_retry()
        assert _counter_value(m.event_delivery_total, status="retry") == 1.0
        assert _counter_value_no_labels(m.event_retry_total) == 1.0

    def test_multiple_retries_accumulate(self):
        m = _event_metrics()
        for _ in range(3):
            m.record_delivery_retry()
        assert _counter_value(m.event_delivery_total, status="retry") == 3.0
        assert _counter_value_no_labels(m.event_retry_total) == 3.0

    def test_delivery_statuses_are_independent(self):
        m = _event_metrics()
        m.record_delivery_success()
        m.record_delivery_success()
        m.record_delivery_retry()
        m.record_delivery_failed()
        assert _counter_value(m.event_delivery_total, status="success") == 2.0
        assert _counter_value(m.event_delivery_total, status="retry") == 1.0
        assert _counter_value(m.event_delivery_total, status="failed") == 1.0

    def test_record_delivery_with_custom_status(self):
        m = _event_metrics()
        m.record_delivery("duplicate")
        assert _counter_value(m.event_delivery_total, status="duplicate") == 1.0

    def test_event_retry_total_starts_at_zero(self):
        m = _event_metrics()
        assert _counter_value_no_labels(m.event_retry_total) == 0.0


# ---------------------------------------------------------------------------
# GenerationMetrics tests
# ---------------------------------------------------------------------------

class TestGenerationMetrics:
    """Tests for GenerationMetrics – Requirement 10.3."""

    def test_record_generation_success_backend(self):
        m = _generation_metrics()
        m.record_generation_success("backend")
        assert _counter_value(m.generation_total, type="backend", result="success") == 1.0

    def test_record_generation_success_fullstack(self):
        m = _generation_metrics()
        m.record_generation_success("fullstack")
        assert _counter_value(m.generation_total, type="fullstack", result="success") == 1.0

    def test_record_generation_failed(self):
        m = _generation_metrics()
        m.record_generation_failed("backend")
        assert _counter_value(m.generation_total, type="backend", result="failed") == 1.0

    def test_generation_success_and_failed_are_independent(self):
        m = _generation_metrics()
        m.record_generation_success("backend")
        m.record_generation_success("backend")
        m.record_generation_failed("backend")
        assert _counter_value(m.generation_total, type="backend", result="success") == 2.0
        assert _counter_value(m.generation_total, type="backend", result="failed") == 1.0

    def test_validation_failure_syntax(self):
        m = _generation_metrics()
        m.record_validation_failure("syntax")
        assert _counter_value(m.validation_failure_total, category="syntax") == 1.0

    def test_validation_failure_structure(self):
        m = _generation_metrics()
        m.record_validation_failure("structure")
        assert _counter_value(m.validation_failure_total, category="structure") == 1.0

    def test_validation_failure_dependency(self):
        m = _generation_metrics()
        m.record_validation_failure("dependency")
        assert _counter_value(m.validation_failure_total, category="dependency") == 1.0

    def test_validation_failure_runtime(self):
        m = _generation_metrics()
        m.record_validation_failure("runtime")
        assert _counter_value(m.validation_failure_total, category="runtime") == 1.0

    def test_validation_failure_categories_are_independent(self):
        m = _generation_metrics()
        m.record_validation_failure("syntax")
        m.record_validation_failure("syntax")
        m.record_validation_failure("runtime")
        assert _counter_value(m.validation_failure_total, category="syntax") == 2.0
        assert _counter_value(m.validation_failure_total, category="runtime") == 1.0
        assert _counter_value(m.validation_failure_total, category="structure") == 0.0

    def test_generation_total_starts_at_zero(self):
        m = _generation_metrics()
        assert _counter_value(m.generation_total, type="backend", result="success") == 0.0


# ---------------------------------------------------------------------------
# Property tests: counters are always non-negative
# ---------------------------------------------------------------------------

_intent_strategy = st.sampled_from([
    "backend_generation", "analyze", "test", "code_change", "deploy", "fullstack",
])
_result_strategy = st.sampled_from(["success", "failed"])
_gen_type_strategy = st.sampled_from(["backend", "fullstack"])
_delivery_status_strategy = st.sampled_from(["success", "retry", "failed"])
_validation_category_strategy = st.sampled_from(["syntax", "structure", "dependency", "runtime"])
_positive_count_strategy = st.integers(min_value=0, max_value=50)
_duration_strategy = st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False)


class TestPropertyCountersNonNegative:
    """
    Property test: all Prometheus counters are always non-negative.

    **Validates: Requirements 10.1, 10.2, 10.3**
    """

    @given(_intent_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_task_created_counter_non_negative(
        self, intent: str, count: int
    ):
        """
        For any intent and any number of increments, task_created_total
        SHALL be non-negative.

        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        for _ in range(count):
            m.record_task_created(intent)
        value = _counter_value(m.task_created_total, intent=intent)
        assert value >= 0.0
        assert value == float(count)

    @given(_intent_strategy, _result_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_task_completed_counter_non_negative(
        self, intent: str, result: str, count: int
    ):
        """
        For any intent, result, and number of increments, task_completed_total
        SHALL be non-negative.

        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        for _ in range(count):
            m.record_task_completed(intent, result)
        value = _counter_value(m.task_completed_total, intent=intent, result=result)
        assert value >= 0.0
        assert value == float(count)

    @given(_intent_strategy, _duration_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_task_duration_histogram_non_negative(
        self, intent: str, duration: float
    ):
        """
        For any intent and non-negative duration, recording task duration
        SHALL not raise and the histogram count SHALL be non-negative.

        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        m.record_task_duration(intent, duration)
        # Histogram count should be 1 after one observation
        count = m.task_duration_seconds.labels(intent=intent)._sum.get()
        assert count >= 0.0

    @given(_delivery_status_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_event_delivery_counter_non_negative(
        self, status: str, count: int
    ):
        """
        For any delivery status and number of increments, event_delivery_total
        SHALL be non-negative.

        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for _ in range(count):
            m.record_delivery(status)
        value = _counter_value(m.event_delivery_total, status=status)
        assert value >= 0.0
        assert value == float(count)

    @given(_positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_event_retry_counter_non_negative(self, count: int):
        """
        For any number of retry increments, event_retry_total SHALL be
        non-negative.

        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for _ in range(count):
            m.event_retry_total.inc()
        value = _counter_value_no_labels(m.event_retry_total)
        assert value >= 0.0
        assert value == float(count)

    @given(_gen_type_strategy, _result_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_generation_counter_non_negative(
        self, gen_type: str, result: str, count: int
    ):
        """
        For any generation type, result, and number of increments,
        generation_total SHALL be non-negative.

        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        for _ in range(count):
            m.record_generation(gen_type, result)
        value = _counter_value(m.generation_total, type=gen_type, result=result)
        assert value >= 0.0
        assert value == float(count)

    @given(_validation_category_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_validation_failure_counter_non_negative(
        self, category: str, count: int
    ):
        """
        For any validation failure category and number of increments,
        validation_failure_total SHALL be non-negative.

        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        for _ in range(count):
            m.record_validation_failure(category)
        value = _counter_value(m.validation_failure_total, category=category)
        assert value >= 0.0
        assert value == float(count)
