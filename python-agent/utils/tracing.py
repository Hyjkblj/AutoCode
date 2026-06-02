"""
Distributed tracing utilities for the Python Agent.

Provides trace context generation, propagation across services via HTTP headers,
and structured log record building with consistent trace correlation fields.

**Validates: Requirements 10.5**
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def generate_trace_id() -> str:
    """Generate a unique trace ID in the format ``trace-{16 hex chars}``."""
    return f"trace-{secrets.token_hex(8)}"


def generate_span_id() -> str:
    """Generate a unique span ID in the format ``span-{12 hex chars}``."""
    return f"span-{secrets.token_hex(6)}"


# ---------------------------------------------------------------------------
# TraceContext dataclass
# ---------------------------------------------------------------------------


@dataclass
class TraceContext:
    """Immutable carrier for distributed trace context."""

    trace_id: str
    span_id: str
    parent_span_id: str
    task_id: str
    service_name: str


# ---------------------------------------------------------------------------
# TraceContextManager
# ---------------------------------------------------------------------------


class TraceContextManager:
    """Factory and serialisation helpers for :class:`TraceContext` objects."""

    # HTTP header names used for propagation
    HEADER_TRACE_ID = "X-Trace-Id"
    HEADER_SPAN_ID = "X-Span-Id"
    HEADER_PARENT_SPAN_ID = "X-Parent-Span-Id"

    def create_root_span(self, task_id: str, service_name: str) -> TraceContext:
        """Create a new root span with a fresh trace ID and no parent span.

        Args:
            task_id: Identifier of the task being traced.
            service_name: Name of the service creating the span.

        Returns:
            A :class:`TraceContext` with a new ``trace_id`` and ``span_id``
            and an empty ``parent_span_id``.
        """
        return TraceContext(
            trace_id=generate_trace_id(),
            span_id=generate_span_id(),
            parent_span_id="",
            task_id=str(task_id),
            service_name=str(service_name),
        )

    def create_child_span(
        self, parent_context: TraceContext, service_name: str
    ) -> TraceContext:
        """Create a child span that inherits the parent's trace ID.

        The child receives a new ``span_id`` and records the parent's
        ``span_id`` as its ``parent_span_id``.

        Args:
            parent_context: The :class:`TraceContext` of the parent span.
            service_name: Name of the service creating the child span.

        Returns:
            A :class:`TraceContext` sharing the parent's ``trace_id`` and
            ``task_id`` but with a new ``span_id``.
        """
        return TraceContext(
            trace_id=parent_context.trace_id,
            span_id=generate_span_id(),
            parent_span_id=parent_context.span_id,
            task_id=parent_context.task_id,
            service_name=str(service_name),
        )

    def to_headers(self, context: TraceContext) -> dict[str, str]:
        """Serialise a :class:`TraceContext` into HTTP propagation headers.

        Args:
            context: The trace context to serialise.

        Returns:
            A dict with ``X-Trace-Id``, ``X-Span-Id``, and
            ``X-Parent-Span-Id`` keys.  ``X-Parent-Span-Id`` is included
            even when empty so that downstream services can detect root spans.
        """
        return {
            self.HEADER_TRACE_ID: context.trace_id,
            self.HEADER_SPAN_ID: context.span_id,
            self.HEADER_PARENT_SPAN_ID: context.parent_span_id,
        }

    def from_headers(self, headers: dict[str, Any]) -> TraceContext | None:
        """Parse a :class:`TraceContext` from HTTP headers.

        Header lookup is case-insensitive to accommodate different HTTP
        frameworks that may normalise header names.

        Args:
            headers: A mapping of header names to values.

        Returns:
            A :class:`TraceContext` if ``X-Trace-Id`` is present and
            non-empty, otherwise ``None``.
        """
        # Build a case-insensitive lookup
        normalised: dict[str, str] = {
            k.lower(): str(v).strip() for k, v in headers.items()
        }

        trace_id = normalised.get(self.HEADER_TRACE_ID.lower(), "")
        if not trace_id:
            return None

        span_id = normalised.get(self.HEADER_SPAN_ID.lower(), "")
        parent_span_id = normalised.get(self.HEADER_PARENT_SPAN_ID.lower(), "")

        return TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            task_id="",
            service_name="",
        )


# ---------------------------------------------------------------------------
# Structured log record builder
# ---------------------------------------------------------------------------


def format_trace_log(
    context: TraceContext,
    event_type: str,
    **fields: Any,
) -> dict[str, Any]:
    """Build a structured log record with all required trace correlation fields.

    The returned dict always contains the mandatory fields required by
    Requirement 10.5: ``taskId``, ``traceId``, ``stage``, and ``errorCode``.
    Additional keyword arguments are merged in, allowing callers to supply
    arbitrary extra context.

    Args:
        context: The active :class:`TraceContext`.
        event_type: A short string identifying the type of event being logged.
        **fields: Optional extra fields to include in the record.  The keys
            ``stage`` and ``errorCode`` are given empty-string defaults if not
            provided by the caller.

    Returns:
        A dict suitable for structured logging.
    """
    record: dict[str, Any] = {
        "eventType": str(event_type),
        "taskId": context.task_id,
        "traceId": context.trace_id,
        "spanId": context.span_id,
        "serviceName": context.service_name,
        # Requirement 10.5 mandatory fields with safe defaults
        "stage": "",
        "errorCode": "",
    }
    # Caller-supplied fields override defaults (except the core identity fields)
    for key, value in fields.items():
        record[key] = value
    return record
