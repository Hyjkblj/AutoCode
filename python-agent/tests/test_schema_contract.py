"""Contract tests: validate Python data structures against shared JSON Schema files.

Ensures that Python-side data conforms to the schema definitions in
shared-protocol/src/main/resources/schema/. Mirrors the Java SchemaContractTest.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from utils.schema_validator import (
    SchemaValidationError,
    validate_ack_response,
    validate_against_schema,
)

# Paths relative to shared-protocol/src/main/resources/schema/
TASK_EVENT_SCHEMA = "events/v1/task_event.v1.schema.json"
SANDBOX_HEALTH_SCHEMA = "sandbox/v1/sandbox_health_response.v1.schema.json"
SANDBOX_EXEC_REQ_SCHEMA = "sandbox/v1/sandbox_execute_request.v1.schema.json"
SANDBOX_EXEC_RESP_SCHEMA = "sandbox/v1/sandbox_execute_response.v1.schema.json"


# -- TaskEvent contract --


class TestTaskEventContract:
    """Validate task event data against task_event.v1.schema.json."""

    def _make_event(self, **overrides) -> dict:
        event = {
            "eventId": "evt-001",
            "taskId": "task-001",
            "type": "TASK_STARTED",
            "timestamp": "2026-05-07T10:00:00Z",
            "seq": 0,
            "eventVersion": 1,
        }
        event.update(overrides)
        return event

    def test_task_event_minimal(self):
        """Minimal task event with required fields only."""
        event = self._make_event()
        validate_against_schema(event, TASK_EVENT_SCHEMA)

    @pytest.mark.parametrize("event_type", [
        "TASK_CREATED", "TASK_STARTED", "ASSISTANT_OUTPUT",
        "TOOL_START", "TOOL_END", "BUILD_STARTED", "BUILD_DONE",
        "TASK_DONE", "TASK_FAILED", "HEARTBEAT",
    ])
    def test_task_event_types(self, event_type: str):
        """All defined event types must pass schema validation."""
        event = self._make_event(type=event_type)
        validate_against_schema(event, TASK_EVENT_SCHEMA)

    def test_task_event_with_optional_fields(self):
        """Event with optional sessionId, assistant, payload."""
        event = self._make_event(
            sessionId="sess-123",
            assistant="coder-agent",
            payload={"key": "value"},
        )
        validate_against_schema(event, TASK_EVENT_SCHEMA)

    def test_task_event_missing_required_field(self):
        """Missing required field must raise SchemaValidationError."""
        event = self._make_event()
        del event["eventId"]
        with pytest.raises(SchemaValidationError, match="eventId"):
            validate_against_schema(event, TASK_EVENT_SCHEMA)

    def test_task_event_bad_seq_type(self):
        """seq must be integer."""
        event = self._make_event(seq="not-a-number")
        with pytest.raises(SchemaValidationError):
            validate_against_schema(event, TASK_EVENT_SCHEMA)


# -- SandboxHealthResponse contract --


class TestSandboxHealthContract:
    """Validate sandbox health response data against schema."""

    def test_health_up(self):
        """Standard up response."""
        data = {"ok": True, "status": "up"}
        validate_against_schema(data, SANDBOX_HEALTH_SCHEMA)

    def test_health_custom_status(self):
        """Custom status string."""
        data = {"ok": True, "status": "healthy"}
        validate_against_schema(data, SANDBOX_HEALTH_SCHEMA)

    def test_health_missing_ok(self):
        """Missing 'ok' field must fail."""
        data = {"status": "up"}
        with pytest.raises(SchemaValidationError, match="ok"):
            validate_against_schema(data, SANDBOX_HEALTH_SCHEMA)


# -- SandboxExecuteRequest contract --


class TestSandboxExecuteRequestContract:
    """Validate sandbox execute request data against schema."""

    def test_request_minimal(self):
        """Minimal request with required fields only."""
        data = {"taskId": "task-001", "command": "echo hello"}
        validate_against_schema(data, SANDBOX_EXEC_REQ_SCHEMA)

    def test_request_full_fields(self):
        """Request with all optional fields."""
        data = {
            "taskId": "task-001",
            "command": "npm test",
            "cwd": "/workspace",
            "prompt": "run tests",
            "tool": "command.exec",
            "action": "run_command",
            "toolVersion": "1.0",
            "traceId": "trace-abc",
            "runId": "run-123",
            "assistant": "coder-agent",
            "sessionId": "sess-1",
            "sessionKey": "key-1",
            "approvalTimeoutSeconds": 60,
        }
        validate_against_schema(data, SANDBOX_EXEC_REQ_SCHEMA)

    def test_request_missing_command(self):
        """Missing 'command' must fail."""
        data = {"taskId": "task-001"}
        with pytest.raises(SchemaValidationError, match="command"):
            validate_against_schema(data, SANDBOX_EXEC_REQ_SCHEMA)


# -- SandboxExecuteResponse contract --


class TestSandboxExecuteResponseContract:
    """Validate sandbox execute response data against schema."""

    def test_response_success(self):
        """Successful execution response."""
        data = {
            "ok": True,
            "status": "completed",
            "retryable": False,
            "exitCode": 0,
            "output": "all tests passed",
        }
        validate_against_schema(data, SANDBOX_EXEC_RESP_SCHEMA)

    def test_response_failure(self):
        """Failed execution response."""
        data = {
            "ok": False,
            "status": "failed",
            "retryable": True,
            "reason": "command not found",
        }
        validate_against_schema(data, SANDBOX_EXEC_RESP_SCHEMA)

    def test_response_with_approval(self):
        """Response requiring approval."""
        data = {
            "ok": False,
            "status": "approval_required",
            "retryable": False,
            "reason": "needs approval",
            "approvalId": "appr-456",
        }
        validate_against_schema(data, SANDBOX_EXEC_RESP_SCHEMA)

    def test_response_missing_required_field(self):
        """Missing required field 'status' must fail."""
        data = {"ok": True, "retryable": False}
        with pytest.raises(SchemaValidationError, match="status"):
            validate_against_schema(data, SANDBOX_EXEC_RESP_SCHEMA)


# -- ACK response contract (supplement existing coverage) --


class TestAckResponseContract:
    """Validate ACK response data against inline schema."""

    def test_ack_accepted(self):
        data = {"seq": 1, "accepted": True, "duplicate": False}
        validate_ack_response(data)

    def test_ack_duplicate(self):
        data = {"seq": 5, "accepted": False, "duplicate": True}
        validate_ack_response(data)

    def test_ack_rejected_with_error(self):
        data = {
            "seq": 3,
            "accepted": False,
            "duplicate": False,
            "errorCode": "PROCESSING_ERROR",
        }
        validate_ack_response(data)

    def test_ack_rejected_with_null_error(self):
        data = {
            "seq": 0,
            "accepted": False,
            "duplicate": False,
            "errorCode": None,
        }
        validate_ack_response(data)
