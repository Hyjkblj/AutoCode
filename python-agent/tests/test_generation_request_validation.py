from __future__ import annotations

from orchestrator.agent_orchestrator import _validate_generation_request


def test_validate_generation_request_accepts_supported_web_zip() -> None:
    assert _validate_generation_request({"target": "web", "exportMode": "zip"}) is None


def test_validate_generation_request_rejects_unsupported_target() -> None:
    payload = _validate_generation_request({"target": "miniapp"})

    assert payload is not None
    assert payload["reason"] == "unsupported_target"


def test_validate_generation_request_rejects_unsupported_export_mode() -> None:
    payload = _validate_generation_request({"target": "web", "exportMode": "git"})

    assert payload is not None
    assert payload["reason"] == "unsupported_export_mode"
