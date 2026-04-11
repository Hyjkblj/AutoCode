from __future__ import annotations

import json
import io
from typing import Any
from urllib.error import HTTPError

import pytest

from tools.exec_tool import ExecTool
from tools.exec_tool import _resolve_cwd


class _StubResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_exec_tool_posts_to_sandbox_execute_and_parses_response(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads((req.data or b"{}").decode("utf-8"))
        return _StubResponse(
            200,
            {
                "ok": True,
                "status": "ok",
                "exitCode": 0,
                "output": "deploy_ok",
                "retryable": False,
                "tool": "deploy.execute",
                "toolVersion": "1.0.0",
                "traceId": "trc_task_200",
                "runId": "run_task_200",
            },
        )

    monkeypatch.setattr("tools.exec_tool.request.urlopen", fake_urlopen)

    tool = ExecTool(base_url="http://127.0.0.1:18080", timeout_seconds=9)
    result = tool.execute(
        task={
            "taskId": "task_200",
            "assistant": "ai-agent",
            "sessionKey": "sess_200",
            "workspacePath": "D:/workspace/demo",
        },
        command="echo deploy",
        prompt="please deploy",
        intent="deploy",
    )

    assert captured["url"] == "http://127.0.0.1:18080/sandbox/execute"
    assert captured["timeout"] == 9
    assert captured["body"]["taskId"] == "task_200"
    assert captured["body"]["command"] == "echo deploy"
    assert captured["body"]["cwd"] == "D:/workspace/demo"
    assert captured["body"]["tool"] == "deploy.execute"
    assert captured["body"]["sessionId"] == "sess_200"
    assert result.ok is True
    assert result.status == "ok"
    assert result.exit_code == 0
    assert result.trace_id == "trc_task_200"


def test_exec_tool_raises_runtime_error_on_http_error(monkeypatch) -> None:
    def fake_urlopen(req, timeout):  # noqa: ANN001
        raise HTTPError(req.full_url, 400, "bad request", hdrs=None, fp=io.BytesIO(b"{\"error\":\"invalid\"}"))

    monkeypatch.setattr("tools.exec_tool.request.urlopen", fake_urlopen)

    tool = ExecTool(base_url="http://127.0.0.1:18080", timeout_seconds=5)
    with pytest.raises(RuntimeError, match="sandbox execute failed: 400"):
        tool.execute(
            task={"taskId": "task_201", "workspacePath": "D:/workspace/demo"},
            command="echo deploy_fail",
            prompt="deploy",
            intent="deploy",
        )


def test_resolve_cwd_treats_none_like_workspace_text_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", "D:/Develop/Project/AutoCode")
    assert _resolve_cwd({"workspacePath": "None"}) == "D:/Develop/Project/AutoCode"
    assert _resolve_cwd({"workspacePath": " null "}) == "D:/Develop/Project/AutoCode"


def test_resolve_cwd_falls_back_to_os_cwd_when_prefix_is_invalid(monkeypatch) -> None:
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", "None, ,null")
    monkeypatch.setattr("os.getcwd", lambda: "D:/fallback/cwd")
    assert _resolve_cwd({"workspacePath": None}) == "D:/fallback/cwd"
