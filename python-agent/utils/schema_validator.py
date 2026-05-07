"""Shared protocol JSON Schema validation for Python agent.

Loads .schema.json files from the shared-protocol module and validates
JSON instances against them. Used for contract testing and runtime validation.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:
    jsonschema = None

_SCHEMA_ROOT = Path(__file__).resolve().parent.parent.parent / "shared-protocol" / "src" / "main" / "resources" / "schema"

# ACK response schema — required fields and errorCode enum
ACK_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["seq", "accepted", "duplicate"],
    "properties": {
        "seq": {"type": "integer", "minimum": 0},
        "accepted": {"type": "boolean"},
        "duplicate": {"type": "boolean"},
        "errorCode": {
            "type": ["string", "null"],
            "enum": [
                None,
                "INVALID_NODE_ID",
                "NODE_NOT_REGISTERED",
                "MISSING_EVENT_ID",
                "TASK_NOT_FOUND",
                "PROCESSING_ERROR",
                "ACCESS_DENIED",
                "INVALID_EVENT",
                "ILLEGAL_STATE_TRANSITION",
            ],
        },
    },
}


class SchemaValidationError(Exception):
    """Raised when a JSON instance fails schema validation."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


@lru_cache(maxsize=16)
def _load_schema_from_file(schema_relative_path: str) -> dict[str, Any]:
    """Load a schema JSON file from the shared-protocol resources."""
    path = _SCHEMA_ROOT / schema_relative_path
    if not path.exists():
        raise FileNotFoundError(f"schema file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_ack_response(data: dict[str, Any]) -> None:
    """Validate an ACK response against the event_ack schema.

    Raises SchemaValidationError if validation fails.
    Uses the inline schema if jsonschema is not available.
    """
    errors = _validate_object(data, ACK_SCHEMA)
    if errors:
        raise SchemaValidationError(
            f"ACK response schema violation: {'; '.join(errors)}",
            errors=errors,
        )


def validate_against_schema(data: dict[str, Any], schema_path: str) -> None:
    """Validate data against a schema file from shared-protocol.

    Args:
        data: JSON instance to validate
        schema_path: Relative path under schema/ directory (e.g. "events/v1/event_ack.v1.schema.json")
    """
    try:
        schema = _load_schema_from_file(schema_path)
    except FileNotFoundError:
        # Fall back to inline schemas for critical paths
        if "event_ack" in schema_path:
            validate_ack_response(data)
            return
        raise

    if jsonschema is not None:
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            raise SchemaValidationError(
                f"schema violation ({schema_path}): {exc.message}",
                errors=[exc.message],
            ) from exc
    else:
        errors = _validate_object(data, schema)
        if errors:
            raise SchemaValidationError(
                f"schema violation ({schema_path}): {'; '.join(errors)}",
                errors=errors,
            )


def _validate_object(data: Any, schema: dict[str, Any]) -> list[str]:
    """Lightweight schema validation without jsonschema dependency.

    Checks: required fields, type, enum, additionalProperties.
    Returns list of error messages (empty = valid).
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"expected object, got {type(data).__name__}"]

    # Required fields
    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"missing required field: {field}")

    # Additional properties
    if schema.get("additionalProperties") is False:
        allowed = set(schema.get("properties", {}).keys())
        for key in data:
            if key not in allowed:
                errors.append(f"additional property not allowed: {key}")

    # Property types and enums
    for prop_name, prop_schema in schema.get("properties", {}).items():
        if prop_name not in data:
            continue
        value = data[prop_name]

        # Type check
        expected_type = prop_schema.get("type")
        if expected_type:
            if isinstance(expected_type, list):
                # Union type like ["string", "null"]
                type_ok = any(_type_matches(value, t) for t in expected_type)
                if not type_ok:
                    errors.append(f"{prop_name}: expected {' or '.join(expected_type)}, got {type(value).__name__}")
            else:
                if not _type_matches(value, expected_type):
                    errors.append(f"{prop_name}: expected {expected_type}, got {type(value).__name__}")

        # Enum check
        enum_values = prop_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            errors.append(f"{prop_name}: value '{value}' not in enum {enum_values}")

        # Minimum check (for integers)
        if "minimum" in prop_schema and isinstance(value, (int, float)):
            if value < prop_schema["minimum"]:
                errors.append(f"{prop_name}: value {value} < minimum {prop_schema['minimum']}")

    return errors


def _type_matches(value: Any, expected_type: str) -> bool:
    """Check if a Python value matches the JSON Schema type."""
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True
