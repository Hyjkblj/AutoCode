"""
Property-based tests for observability infrastructure.

Task 26.4: Write property tests for observability
Property 34: Metrics Exposure
Validates: Requirements 9.7, 10.1, 10.2, 10.3

These tests validate that Prometheus metrics are correctly exposed for task
lifecycle events, event delivery, backend generation, and that structured logs
always contain the required trace correlation fields.
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st
from prometheus_client import CollectorRegistry

from utils.metrics import EventMetrics, GenerationMetrics, TaskMetrics
from utils.tracing import TraceContext, TraceContextManager, format_trace_log


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
# Strategies
# ---------------------------------------------------------------------------

_intent_strategy = st.text(
    min_size=1,
    max_size=40,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
)

_result_strategy = st.sampled_from(["success", "failed"])

_gen_type_strategy = st.sampled_from(["backend", "fullstack"])

_delivery_status_strategy = st.sampled_from(["success", "retry", "failed"])

_validation_category_strategy = st.sampled_from(
    ["syntax", "structure", "dependency", "runtime"]
)

_positive_count_strategy = st.integers(min_value=0, max_value=50)

_event_type_strategy = st.text(
    min_size=1,
    max_size=40,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
)

_task_id_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
)

_service_name_strategy = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
)


# ---------------------------------------------------------------------------
# Property 34a: TaskMetrics counters are always non-negative
# ---------------------------------------------------------------------------

class TestProperty34aTaskMetricsNonNegative:
    """
    Property 34a: TaskMetrics counters are always non-negative.

    For any sequence of task_created/completed recordings, all counter
    values SHALL be >= 0.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 10.1**
    """

    @given(_intent_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_task_created_counter_always_non_negative(
        self, intent: str, count: int
    ) -> None:
        """
        For any intent and any number of record_task_created calls,
        task_created_total SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        for _ in range(count):
            m.record_task_created(intent)
        value = _counter_value(m.task_created_total, intent=intent)
        assert value >= 0.0, f"task_created_total must be non-negative, got {value}"

    @given(_intent_strategy, _result_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_task_completed_counter_always_non_negative(
        self, intent: str, result: str, count: int
    ) -> None:
        """
        For any intent, result, and number of record_task_completed calls,
        task_completed_total SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        for _ in range(count):
            m.record_task_completed(intent, result)
        value = _counter_value(m.task_completed_total, intent=intent, result=result)
        assert value >= 0.0, f"task_completed_total must be non-negative, got {value}"

    @given(_intent_strategy, _positive_count_strategy, _result_strategy)
    @settings(max_examples=50, deadline=None)
    def test_mixed_task_recordings_all_non_negative(
        self, intent: str, count: int, result: str
    ) -> None:
        """
        For any sequence of mixed task_created and task_completed recordings,
        all counter values SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        for i in range(count):
            m.record_task_created(intent)
            if i % 2 == 0:
                m.record_task_completed(intent, result)

        created_value = _counter_value(m.task_created_total, intent=intent)
        completed_value = _counter_value(
            m.task_completed_total, intent=intent, result=result
        )
        assert created_value >= 0.0
        assert completed_value >= 0.0


# ---------------------------------------------------------------------------
# Property 34b: EventMetrics counters are always non-negative
# ---------------------------------------------------------------------------

class TestProperty34bEventMetricsNonNegative:
    """
    Property 34b: EventMetrics counters are always non-negative.

    For any sequence of delivery recordings, all counter values SHALL be >= 0.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 10.2**
    """

    @given(_delivery_status_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_event_delivery_counter_always_non_negative(
        self, status: str, count: int
    ) -> None:
        """
        For any delivery status and any number of record_delivery calls,
        event_delivery_total SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for _ in range(count):
            m.record_delivery(status)
        value = _counter_value(m.event_delivery_total, status=status)
        assert value >= 0.0, f"event_delivery_total must be non-negative, got {value}"

    @given(_positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_event_retry_total_always_non_negative(self, count: int) -> None:
        """
        For any number of record_delivery_retry calls, event_retry_total
        SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for _ in range(count):
            m.record_delivery_retry()
        value = _counter_value_no_labels(m.event_retry_total)
        assert value >= 0.0, f"event_retry_total must be non-negative, got {value}"

    @given(_positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_all_event_counters_non_negative_after_mixed_recordings(
        self, count: int
    ) -> None:
        """
        For any sequence of mixed success/retry/failed recordings, all
        event_delivery_total label values SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for i in range(count):
            if i % 3 == 0:
                m.record_delivery_success()
            elif i % 3 == 1:
                m.record_delivery_retry()
            else:
                m.record_delivery_failed()

        for status in ("success", "retry", "failed"):
            value = _counter_value(m.event_delivery_total, status=status)
            assert value >= 0.0, (
                f"event_delivery_total[{status}] must be non-negative, got {value}"
            )
        retry_total = _counter_value_no_labels(m.event_retry_total)
        assert retry_total >= 0.0


# ---------------------------------------------------------------------------
# Property 34c: GenerationMetrics counters are always non-negative
# ---------------------------------------------------------------------------

class TestProperty34cGenerationMetricsNonNegative:
    """
    Property 34c: GenerationMetrics counters are always non-negative.

    For any sequence of generation recordings, all counter values SHALL be >= 0.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 10.3**
    """

    @given(_gen_type_strategy, _result_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_generation_total_always_non_negative(
        self, gen_type: str, result: str, count: int
    ) -> None:
        """
        For any generation type, result, and number of record_generation calls,
        generation_total SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        for _ in range(count):
            m.record_generation(gen_type, result)
        value = _counter_value(m.generation_total, type=gen_type, result=result)
        assert value >= 0.0, f"generation_total must be non-negative, got {value}"

    @given(_validation_category_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_validation_failure_total_always_non_negative(
        self, category: str, count: int
    ) -> None:
        """
        For any validation failure category and number of recordings,
        validation_failure_total SHALL be >= 0.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        for _ in range(count):
            m.record_validation_failure(category)
        value = _counter_value(m.validation_failure_total, category=category)
        assert value >= 0.0, (
            f"validation_failure_total[{category}] must be non-negative, got {value}"
        )


# ---------------------------------------------------------------------------
# Property 34d: TaskMetrics records correct intent labels
# ---------------------------------------------------------------------------

class TestProperty34dTaskMetricsIntentLabels:
    """
    Property 34d: TaskMetrics records correct intent labels.

    For any intent string, record_task_created(intent) SHALL increment the
    counter for that specific intent and only that intent.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 10.1**
    """

    @given(_intent_strategy)
    @settings(max_examples=50, deadline=None)
    def test_record_task_created_increments_correct_intent(
        self, intent: str
    ) -> None:
        """
        For any intent string, record_task_created(intent) SHALL increment
        task_created_total for that intent by exactly 1.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        before = _counter_value(m.task_created_total, intent=intent)
        m.record_task_created(intent)
        after = _counter_value(m.task_created_total, intent=intent)
        assert after - before == 1.0, (
            f"record_task_created('{intent}') must increment counter by 1, "
            f"got delta {after - before}"
        )

    @given(_intent_strategy, _intent_strategy)
    @settings(max_examples=50, deadline=None)
    def test_record_task_created_does_not_affect_other_intents(
        self, intent_a: str, intent_b: str
    ) -> None:
        """
        For any two distinct intents, recording task_created for intent_a
        SHALL NOT affect the counter for intent_b.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.1**
        """
        from hypothesis import assume
        assume(intent_a != intent_b)

        m = _task_metrics()
        before_b = _counter_value(m.task_created_total, intent=intent_b)
        m.record_task_created(intent_a)
        after_b = _counter_value(m.task_created_total, intent=intent_b)
        assert after_b == before_b, (
            f"Recording intent '{intent_a}' must not affect counter for '{intent_b}'"
        )

    @given(_intent_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_record_task_created_counter_equals_call_count(
        self, intent: str, count: int
    ) -> None:
        """
        For any intent and N calls to record_task_created, the counter
        SHALL equal exactly N.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.1**
        """
        m = _task_metrics()
        for _ in range(count):
            m.record_task_created(intent)
        value = _counter_value(m.task_created_total, intent=intent)
        assert value == float(count), (
            f"task_created_total[{intent}] must equal {count}, got {value}"
        )


# ---------------------------------------------------------------------------
# Property 34e: EventMetrics retry increments both counters
# ---------------------------------------------------------------------------

class TestProperty34eEventMetricsRetryBothCounters:
    """
    Property 34e: EventMetrics retry increments both counters.

    record_delivery_retry() SHALL increment both
    event_delivery_total{status="retry"} and event_retry_total.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 10.2**
    """

    @given(_positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_record_delivery_retry_increments_both_counters(
        self, count: int
    ) -> None:
        """
        For any number of record_delivery_retry calls, both
        event_delivery_total{status="retry"} and event_retry_total SHALL
        equal the call count.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for _ in range(count):
            m.record_delivery_retry()

        delivery_retry = _counter_value(m.event_delivery_total, status="retry")
        retry_total = _counter_value_no_labels(m.event_retry_total)

        assert delivery_retry == float(count), (
            f"event_delivery_total[retry] must equal {count}, got {delivery_retry}"
        )
        assert retry_total == float(count), (
            f"event_retry_total must equal {count}, got {retry_total}"
        )

    @given(_positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_retry_counters_stay_in_sync(self, count: int) -> None:
        """
        For any number of retry recordings, event_delivery_total{status="retry"}
        and event_retry_total SHALL always be equal.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for _ in range(count):
            m.record_delivery_retry()

        delivery_retry = _counter_value(m.event_delivery_total, status="retry")
        retry_total = _counter_value_no_labels(m.event_retry_total)
        assert delivery_retry == retry_total, (
            f"event_delivery_total[retry]={delivery_retry} must equal "
            f"event_retry_total={retry_total}"
        )

    def test_record_delivery_retry_increments_by_one_per_call(self) -> None:
        """
        Each call to record_delivery_retry() SHALL increment both counters
        by exactly 1.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.2**
        """
        m = _event_metrics()
        for expected in range(1, 6):
            m.record_delivery_retry()
            delivery_retry = _counter_value(m.event_delivery_total, status="retry")
            retry_total = _counter_value_no_labels(m.event_retry_total)
            assert delivery_retry == float(expected)
            assert retry_total == float(expected)


# ---------------------------------------------------------------------------
# Property 34f: GenerationMetrics validation failure categories are tracked
# ---------------------------------------------------------------------------

class TestProperty34fGenerationMetricsValidationCategories:
    """
    Property 34f: GenerationMetrics validation failure categories are tracked.

    For any category in {syntax, structure, dependency, runtime},
    record_validation_failure(category) SHALL increment the correct counter.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 10.3**
    """

    @given(_validation_category_strategy)
    @settings(max_examples=50, deadline=None)
    def test_record_validation_failure_increments_correct_category(
        self, category: str
    ) -> None:
        """
        For any category in {syntax, structure, dependency, runtime},
        record_validation_failure(category) SHALL increment
        validation_failure_total[category] by exactly 1.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        before = _counter_value(m.validation_failure_total, category=category)
        m.record_validation_failure(category)
        after = _counter_value(m.validation_failure_total, category=category)
        assert after - before == 1.0, (
            f"record_validation_failure('{category}') must increment counter by 1, "
            f"got delta {after - before}"
        )

    @given(_validation_category_strategy, _validation_category_strategy)
    @settings(max_examples=50, deadline=None)
    def test_validation_failure_does_not_affect_other_categories(
        self, category_a: str, category_b: str
    ) -> None:
        """
        For any two distinct categories, recording a failure for category_a
        SHALL NOT affect the counter for category_b.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.3**
        """
        from hypothesis import assume
        assume(category_a != category_b)

        m = _generation_metrics()
        before_b = _counter_value(m.validation_failure_total, category=category_b)
        m.record_validation_failure(category_a)
        after_b = _counter_value(m.validation_failure_total, category=category_b)
        assert after_b == before_b, (
            f"Recording category '{category_a}' must not affect counter for '{category_b}'"
        )

    def test_all_four_validation_categories_are_tracked_independently(self) -> None:
        """
        All four validation failure categories (syntax, structure, dependency,
        runtime) SHALL be tracked independently.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        categories = ["syntax", "structure", "dependency", "runtime"]

        # Record different counts for each category
        for i, cat in enumerate(categories, start=1):
            for _ in range(i):
                m.record_validation_failure(cat)

        for i, cat in enumerate(categories, start=1):
            value = _counter_value(m.validation_failure_total, category=cat)
            assert value == float(i), (
                f"validation_failure_total[{cat}] must equal {i}, got {value}"
            )

    @given(_validation_category_strategy, _positive_count_strategy)
    @settings(max_examples=50, deadline=None)
    def test_validation_failure_counter_equals_call_count(
        self, category: str, count: int
    ) -> None:
        """
        For any category and N calls to record_validation_failure, the counter
        SHALL equal exactly N.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 10.3**
        """
        m = _generation_metrics()
        for _ in range(count):
            m.record_validation_failure(category)
        value = _counter_value(m.validation_failure_total, category=category)
        assert value == float(count), (
            f"validation_failure_total[{category}] must equal {count}, got {value}"
        )


# ---------------------------------------------------------------------------
# Property 34g: Structured logs always have required fields
# ---------------------------------------------------------------------------

class TestProperty34gStructuredLogsRequiredFields:
    """
    Property 34g: Structured logs always have required fields.

    For any trace context and event type, format_trace_log() SHALL always
    return a dict with taskId, traceId, stage, and errorCode.

    **Property 34: Metrics Exposure**
    **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
    """

    def _make_context(self, task_id: str, service_name: str) -> TraceContext:
        """Create a TraceContext using the TraceContextManager."""
        manager = TraceContextManager()
        return manager.create_root_span(task_id=task_id, service_name=service_name)

    @given(_task_id_strategy, _service_name_strategy, _event_type_strategy)
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_always_has_required_fields(
        self, task_id: str, service_name: str, event_type: str
    ) -> None:
        """
        For any trace context and event type, format_trace_log() SHALL return
        a dict containing taskId, traceId, stage, and errorCode.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(context, event_type)

        required_fields = {"taskId", "traceId", "stage", "errorCode"}
        for field in required_fields:
            assert field in log_record, (
                f"format_trace_log() must always include '{field}' field, "
                f"got keys: {set(log_record.keys())}"
            )

    @given(_task_id_strategy, _service_name_strategy, _event_type_strategy)
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_task_id_matches_context(
        self, task_id: str, service_name: str, event_type: str
    ) -> None:
        """
        For any trace context, format_trace_log() SHALL set taskId to the
        context's task_id.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(context, event_type)
        assert log_record["taskId"] == str(task_id), (
            f"taskId in log must match context.task_id: "
            f"expected '{task_id}', got '{log_record['taskId']}'"
        )

    @given(_task_id_strategy, _service_name_strategy, _event_type_strategy)
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_trace_id_matches_context(
        self, task_id: str, service_name: str, event_type: str
    ) -> None:
        """
        For any trace context, format_trace_log() SHALL set traceId to the
        context's trace_id.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(context, event_type)
        assert log_record["traceId"] == context.trace_id, (
            f"traceId in log must match context.trace_id: "
            f"expected '{context.trace_id}', got '{log_record['traceId']}'"
        )

    @given(_task_id_strategy, _service_name_strategy, _event_type_strategy)
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_stage_has_default_value(
        self, task_id: str, service_name: str, event_type: str
    ) -> None:
        """
        For any trace context and event type without explicit stage,
        format_trace_log() SHALL include a 'stage' field (defaulting to "").

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(context, event_type)
        assert "stage" in log_record
        # Default stage is empty string when not provided
        assert isinstance(log_record["stage"], str)

    @given(_task_id_strategy, _service_name_strategy, _event_type_strategy)
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_error_code_has_default_value(
        self, task_id: str, service_name: str, event_type: str
    ) -> None:
        """
        For any trace context and event type without explicit errorCode,
        format_trace_log() SHALL include an 'errorCode' field (defaulting to "").

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(context, event_type)
        assert "errorCode" in log_record
        # Default errorCode is empty string when not provided
        assert isinstance(log_record["errorCode"], str)

    @given(
        _task_id_strategy,
        _service_name_strategy,
        _event_type_strategy,
        st.text(min_size=1, max_size=20),
        st.text(min_size=0, max_size=20),
    )
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_caller_supplied_stage_and_error_code(
        self,
        task_id: str,
        service_name: str,
        event_type: str,
        stage: str,
        error_code: str,
    ) -> None:
        """
        For any trace context with caller-supplied stage and errorCode,
        format_trace_log() SHALL include those values in the returned dict.

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(
            context, event_type, stage=stage, errorCode=error_code
        )
        assert log_record["stage"] == stage, (
            f"stage must be '{stage}', got '{log_record['stage']}'"
        )
        assert log_record["errorCode"] == error_code, (
            f"errorCode must be '{error_code}', got '{log_record['errorCode']}'"
        )

    @given(_task_id_strategy, _service_name_strategy, _event_type_strategy)
    @settings(max_examples=50, deadline=None)
    def test_format_trace_log_returns_dict(
        self, task_id: str, service_name: str, event_type: str
    ) -> None:
        """
        For any trace context and event type, format_trace_log() SHALL
        return a dict (not None, not a list, not a string).

        **Property 34: Metrics Exposure**
        **Validates: Requirements 9.7, 10.1, 10.2, 10.3**
        """
        context = self._make_context(task_id, service_name)
        log_record = format_trace_log(context, event_type)
        assert isinstance(log_record, dict), (
            f"format_trace_log() must return a dict, got {type(log_record)}"
        )
