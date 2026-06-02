"""
Tests for distributed tracing utilities (python-agent/utils/tracing.py).

Covers:
- Trace ID and span ID generation (format, uniqueness)
- TraceContextManager.create_root_span()
- TraceContextManager.create_child_span() (inherits trace_id, new span_id)
- to_headers() / from_headers() round-trip
- format_trace_log() (all required fields present)
- Property test: for any trace context, to_headers() → from_headers() preserves trace_id

**Validates: Requirements 10.5**
"""
from __future__ import annotations

import re

import pytest
from hypothesis import given, settings, strategies as st

from utils.tracing import (
    TraceContext,
    TraceContextManager,
    format_trace_log,
    generate_span_id,
    generate_trace_id,
)


# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

TRACE_ID_PATTERN = re.compile(r"^trace-[0-9a-f]{16}$")
SPAN_ID_PATTERN = re.compile(r"^span-[0-9a-f]{12}$")

manager = TraceContextManager()

# Hypothesis strategies for generating arbitrary task/service names
task_id_strategy = st.text(min_size=1, max_size=64).filter(str.strip)
service_name_strategy = st.text(min_size=1, max_size=64).filter(str.strip)


# ---------------------------------------------------------------------------
# Trace ID generation
# ---------------------------------------------------------------------------


class TestGenerateTraceId:
    def test_format_matches_pattern(self):
        """generate_trace_id() SHALL return a string matching 'trace-{16 hex chars}'."""
        tid = generate_trace_id()
        assert TRACE_ID_PATTERN.match(tid), f"Unexpected format: {tid!r}"

    def test_uniqueness(self):
        """generate_trace_id() SHALL return distinct values on successive calls."""
        ids = {generate_trace_id() for _ in range(100)}
        assert len(ids) == 100, "Expected 100 unique trace IDs"

    def test_returns_string(self):
        assert isinstance(generate_trace_id(), str)


# ---------------------------------------------------------------------------
# Span ID generation
# ---------------------------------------------------------------------------


class TestGenerateSpanId:
    def test_format_matches_pattern(self):
        """generate_span_id() SHALL return a string matching 'span-{12 hex chars}'."""
        sid = generate_span_id()
        assert SPAN_ID_PATTERN.match(sid), f"Unexpected format: {sid!r}"

    def test_uniqueness(self):
        """generate_span_id() SHALL return distinct values on successive calls."""
        ids = {generate_span_id() for _ in range(100)}
        assert len(ids) == 100, "Expected 100 unique span IDs"

    def test_returns_string(self):
        assert isinstance(generate_span_id(), str)


# ---------------------------------------------------------------------------
# TraceContextManager.create_root_span
# ---------------------------------------------------------------------------


class TestCreateRootSpan:
    def test_returns_trace_context(self):
        ctx = manager.create_root_span("task-1", "svc-a")
        assert isinstance(ctx, TraceContext)

    def test_trace_id_format(self):
        ctx = manager.create_root_span("task-1", "svc-a")
        assert TRACE_ID_PATTERN.match(ctx.trace_id), f"Bad trace_id: {ctx.trace_id!r}"

    def test_span_id_format(self):
        ctx = manager.create_root_span("task-1", "svc-a")
        assert SPAN_ID_PATTERN.match(ctx.span_id), f"Bad span_id: {ctx.span_id!r}"

    def test_parent_span_id_is_empty(self):
        """Root spans SHALL have no parent span."""
        ctx = manager.create_root_span("task-1", "svc-a")
        assert ctx.parent_span_id == ""

    def test_task_id_preserved(self):
        ctx = manager.create_root_span("my-task-42", "svc-a")
        assert ctx.task_id == "my-task-42"

    def test_service_name_preserved(self):
        ctx = manager.create_root_span("task-1", "python-agent")
        assert ctx.service_name == "python-agent"

    def test_successive_root_spans_have_different_trace_ids(self):
        ctx1 = manager.create_root_span("t1", "svc")
        ctx2 = manager.create_root_span("t2", "svc")
        assert ctx1.trace_id != ctx2.trace_id


# ---------------------------------------------------------------------------
# TraceContextManager.create_child_span
# ---------------------------------------------------------------------------


class TestCreateChildSpan:
    def setup_method(self):
        self.parent = manager.create_root_span("task-99", "parent-svc")

    def test_returns_trace_context(self):
        child = manager.create_child_span(self.parent, "child-svc")
        assert isinstance(child, TraceContext)

    def test_inherits_trace_id(self):
        """Child span SHALL share the parent's trace_id."""
        child = manager.create_child_span(self.parent, "child-svc")
        assert child.trace_id == self.parent.trace_id

    def test_new_span_id(self):
        """Child span SHALL have a different span_id from the parent."""
        child = manager.create_child_span(self.parent, "child-svc")
        assert child.span_id != self.parent.span_id

    def test_span_id_format(self):
        child = manager.create_child_span(self.parent, "child-svc")
        assert SPAN_ID_PATTERN.match(child.span_id)

    def test_parent_span_id_set_to_parent_span(self):
        """Child's parent_span_id SHALL equal the parent's span_id."""
        child = manager.create_child_span(self.parent, "child-svc")
        assert child.parent_span_id == self.parent.span_id

    def test_inherits_task_id(self):
        """Child span SHALL share the parent's task_id."""
        child = manager.create_child_span(self.parent, "child-svc")
        assert child.task_id == self.parent.task_id

    def test_service_name_overridden(self):
        child = manager.create_child_span(self.parent, "downstream-svc")
        assert child.service_name == "downstream-svc"

    def test_grandchild_chain(self):
        """Chained child spans SHALL all share the same trace_id."""
        child = manager.create_child_span(self.parent, "svc-b")
        grandchild = manager.create_child_span(child, "svc-c")
        assert grandchild.trace_id == self.parent.trace_id
        assert grandchild.parent_span_id == child.span_id


# ---------------------------------------------------------------------------
# to_headers / from_headers round-trip
# ---------------------------------------------------------------------------


class TestHeaderRoundTrip:
    def setup_method(self):
        self.ctx = manager.create_root_span("task-rt", "svc-rt")

    def test_to_headers_returns_dict(self):
        headers = manager.to_headers(self.ctx)
        assert isinstance(headers, dict)

    def test_to_headers_contains_required_keys(self):
        headers = manager.to_headers(self.ctx)
        assert "X-Trace-Id" in headers
        assert "X-Span-Id" in headers
        assert "X-Parent-Span-Id" in headers

    def test_to_headers_values_match_context(self):
        headers = manager.to_headers(self.ctx)
        assert headers["X-Trace-Id"] == self.ctx.trace_id
        assert headers["X-Span-Id"] == self.ctx.span_id
        assert headers["X-Parent-Span-Id"] == self.ctx.parent_span_id

    def test_from_headers_returns_trace_context(self):
        headers = manager.to_headers(self.ctx)
        parsed = manager.from_headers(headers)
        assert isinstance(parsed, TraceContext)

    def test_round_trip_preserves_trace_id(self):
        headers = manager.to_headers(self.ctx)
        parsed = manager.from_headers(headers)
        assert parsed is not None
        assert parsed.trace_id == self.ctx.trace_id

    def test_round_trip_preserves_span_id(self):
        headers = manager.to_headers(self.ctx)
        parsed = manager.from_headers(headers)
        assert parsed is not None
        assert parsed.span_id == self.ctx.span_id

    def test_round_trip_preserves_parent_span_id(self):
        parent = manager.create_root_span("task-p", "svc-p")
        child = manager.create_child_span(parent, "svc-c")
        headers = manager.to_headers(child)
        parsed = manager.from_headers(headers)
        assert parsed is not None
        assert parsed.parent_span_id == child.parent_span_id

    def test_from_headers_case_insensitive(self):
        """from_headers() SHALL work regardless of header name casing."""
        headers = {
            "x-trace-id": self.ctx.trace_id,
            "x-span-id": self.ctx.span_id,
            "x-parent-span-id": self.ctx.parent_span_id,
        }
        parsed = manager.from_headers(headers)
        assert parsed is not None
        assert parsed.trace_id == self.ctx.trace_id

    def test_from_headers_missing_trace_id_returns_none(self):
        """from_headers() SHALL return None when X-Trace-Id is absent."""
        parsed = manager.from_headers({"X-Span-Id": "span-abc123456789"})
        assert parsed is None

    def test_from_headers_empty_trace_id_returns_none(self):
        parsed = manager.from_headers({"X-Trace-Id": "", "X-Span-Id": "span-abc123456789"})
        assert parsed is None

    def test_from_headers_empty_dict_returns_none(self):
        assert manager.from_headers({}) is None


# ---------------------------------------------------------------------------
# format_trace_log
# ---------------------------------------------------------------------------


class TestFormatTraceLog:
    def setup_method(self):
        self.ctx = manager.create_root_span("task-log", "log-svc")

    def test_returns_dict(self):
        record = format_trace_log(self.ctx, "test_event")
        assert isinstance(record, dict)

    def test_contains_task_id(self):
        """Requirement 10.5: structured log SHALL include taskId."""
        record = format_trace_log(self.ctx, "test_event")
        assert "taskId" in record
        assert record["taskId"] == self.ctx.task_id

    def test_contains_trace_id(self):
        """Requirement 10.5: structured log SHALL include traceId."""
        record = format_trace_log(self.ctx, "test_event")
        assert "traceId" in record
        assert record["traceId"] == self.ctx.trace_id

    def test_contains_stage(self):
        """Requirement 10.5: structured log SHALL include stage field."""
        record = format_trace_log(self.ctx, "test_event")
        assert "stage" in record

    def test_contains_error_code(self):
        """Requirement 10.5: structured log SHALL include errorCode field."""
        record = format_trace_log(self.ctx, "test_event")
        assert "errorCode" in record

    def test_contains_event_type(self):
        record = format_trace_log(self.ctx, "my_event")
        assert record["eventType"] == "my_event"

    def test_extra_fields_included(self):
        record = format_trace_log(self.ctx, "deploy", stage="coder", errorCode="TIMEOUT")
        assert record["stage"] == "coder"
        assert record["errorCode"] == "TIMEOUT"

    def test_stage_default_is_empty_string(self):
        record = format_trace_log(self.ctx, "event")
        assert record["stage"] == ""

    def test_error_code_default_is_empty_string(self):
        record = format_trace_log(self.ctx, "event")
        assert record["errorCode"] == ""

    def test_arbitrary_extra_fields_merged(self):
        record = format_trace_log(self.ctx, "event", durationMs=42, retryCount=3)
        assert record["durationMs"] == 42
        assert record["retryCount"] == 3


# ---------------------------------------------------------------------------
# Property test: to_headers → from_headers preserves trace_id
# ---------------------------------------------------------------------------


class TestProperty10_5TraceHeaderRoundTrip:
    """
    **Property: for any trace context, to_headers() → from_headers() preserves trace_id.**

    **Validates: Requirements 10.5**
    """

    @given(task_id_strategy, service_name_strategy)
    @settings(max_examples=100, deadline=None)
    def test_root_span_header_round_trip_preserves_trace_id(
        self, task_id: str, service_name: str
    ):
        """
        For any task_id and service_name, a root span serialised to headers
        and parsed back SHALL yield the same trace_id.

        **Validates: Requirements 10.5**
        """
        ctx = manager.create_root_span(task_id, service_name)
        headers = manager.to_headers(ctx)
        parsed = manager.from_headers(headers)

        assert parsed is not None, "from_headers() returned None for valid headers"
        assert parsed.trace_id == ctx.trace_id

    @given(task_id_strategy, service_name_strategy, service_name_strategy)
    @settings(max_examples=100, deadline=None)
    def test_child_span_header_round_trip_preserves_trace_id(
        self, task_id: str, parent_svc: str, child_svc: str
    ):
        """
        For any child span, serialising to headers and parsing back SHALL
        preserve the trace_id (which is shared with the parent).

        **Validates: Requirements 10.5**
        """
        parent = manager.create_root_span(task_id, parent_svc)
        child = manager.create_child_span(parent, child_svc)
        headers = manager.to_headers(child)
        parsed = manager.from_headers(headers)

        assert parsed is not None
        assert parsed.trace_id == child.trace_id
        assert parsed.trace_id == parent.trace_id

    @given(task_id_strategy, service_name_strategy)
    @settings(max_examples=100, deadline=None)
    def test_format_trace_log_always_has_required_fields(
        self, task_id: str, service_name: str
    ):
        """
        For any trace context, format_trace_log() SHALL always include
        taskId, traceId, stage, and errorCode (Requirement 10.5).

        **Validates: Requirements 10.5**
        """
        ctx = manager.create_root_span(task_id, service_name)
        record = format_trace_log(ctx, "any_event")

        assert "taskId" in record
        assert "traceId" in record
        assert "stage" in record
        assert "errorCode" in record
