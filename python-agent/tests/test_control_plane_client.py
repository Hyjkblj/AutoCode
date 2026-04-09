from __future__ import annotations

import json
from typing import Any

from client.control_plane_client import ControlPlaneClient


class _StubResponse:
    def __init__(self, status: int, payload: dict[str, Any] | None) -> None:
        self.status = status
        self._body = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_poll_next_task_uses_ai_agent_profile(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        return _StubResponse(200, {"ok": True, "payload": {"taskId": "task_1"}})

    monkeypatch.setattr("client.control_plane_client.request.urlopen", fake_urlopen)

    client = ControlPlaneClient("http://localhost:8048", "token")
    task = client.poll_next_task("node-ai-1", profile="ai-agent")

    assert task is not None
    assert task["taskId"] == "task_1"
    assert "nodeId=node-ai-1" in captured["url"]
    assert "profile=ai-agent" in captured["url"]


def test_register_posts_capabilities(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads((req.data or b"{}").decode("utf-8"))
        return _StubResponse(200, {"ok": True, "payload": {"nodeId": "node-ai-1"}})

    monkeypatch.setattr("client.control_plane_client.request.urlopen", fake_urlopen)

    client = ControlPlaneClient("http://localhost:8048", "token", agent_version="0.2.0")
    payload = client.register("node-ai-1", capabilities="ai-agent,profile:ai-agent")

    assert payload is not None
    assert payload["nodeId"] == "node-ai-1"
    assert captured["url"].endswith("/api/v1/agent/register")
    assert captured["body"]["nodeId"] == "node-ai-1"
    assert captured["body"]["version"] == "0.2.0"
    assert captured["body"]["capabilities"] == "ai-agent,profile:ai-agent"
    assert captured["headers"]["User-agent"] == "AutoCode-Python-Agent/0.2.0"


def test_upload_artifact_posts_multipart(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}
    artifact = tmp_path / "export.zip"
    artifact.write_bytes(b"zip-bytes")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data
        return _StubResponse(200, {"ok": True, "payload": {"artifactId": "art_1", "name": "export.zip"}})

    monkeypatch.setattr("client.control_plane_client.request.urlopen", fake_urlopen)

    client = ControlPlaneClient("http://localhost:8048", "token")
    payload = client.upload_artifact("task_42", str(artifact), name="export.zip", content_type="application/zip")

    assert payload is not None
    assert payload["artifactId"] == "art_1"
    assert captured["url"].endswith("/api/v1/tasks/task_42/artifacts")
    assert "multipart/form-data" in captured["headers"]["Content-type"]
    body = captured["body"].decode("utf-8", errors="ignore")
    assert 'name="file"; filename="export.zip"' in body
    assert 'name="name"' in body

