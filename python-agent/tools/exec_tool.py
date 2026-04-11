from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import request
from urllib.error import HTTPError
from urllib.error import URLError


@dataclass(frozen=True)
class ExecResult:
    ok: bool
    status: str
    exit_code: int | None
    output: str
    retryable: bool
    reason: str | None
    tool: str | None
    tool_version: str | None
    trace_id: str | None
    run_id: str | None
    approval_id: str | None


class ExecTool:
    def __init__(self, base_url: str | None = None, timeout_seconds: int | None = None) -> None:
        self.base_url = (base_url or os.getenv("MVP_SANDBOX_BASE_URL", "http://127.0.0.1:18080")).rstrip("/")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _read_timeout_seconds()

    def execute(self, task: dict[str, Any], command: str, *, prompt: str = "", intent: str = "deploy") -> ExecResult:
        task_id = str(task.get("taskId", "")).strip()
        if not task_id:
            raise ValueError("task.taskId is required")
        cmd = str(command or "").strip()
        if not cmd:
            raise ValueError("command is required")

        body = {
            "taskId": task_id,
            "command": cmd,
            "cwd": _resolve_cwd(task),
            "prompt": prompt,
            "tool": "deploy.execute" if intent == "deploy" else "command.exec",
            "action": "run_command",
            "assistant": str(task.get("assistant", "")).strip() or "ai-agent",
            "sessionId": _first_non_blank(task.get("sessionId"), task.get("sessionKey")),
            "sessionKey": _first_non_blank(task.get("sessionKey"), task.get("sessionId")),
        }
        if "approvalTimeoutSeconds" in task and task.get("approvalTimeoutSeconds") is not None:
            body["approvalTimeoutSeconds"] = task.get("approvalTimeoutSeconds")

        response = self._post_json("/sandbox/execute", body)
        return ExecResult(
            ok=bool(response.get("ok", False)),
            status=str(response.get("status", "")).strip() or "unknown",
            exit_code=_to_int(response.get("exitCode")),
            output=str(response.get("output", "") or ""),
            retryable=bool(response.get("retryable", False)),
            reason=_blank_to_none(response.get("reason")),
            tool=_blank_to_none(response.get("tool")),
            tool_version=_blank_to_none(response.get("toolVersion")),
            trace_id=_blank_to_none(response.get("traceId")),
            run_id=_blank_to_none(response.get("runId")),
            approval_id=_blank_to_none(response.get("approvalId")),
        )

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        req = request.Request(
            url=url,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "AutoCode-Python-Agent/exec-tool",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace").strip()
                if not raw:
                    return {}
                decoded = json.loads(raw)
                if not isinstance(decoded, dict):
                    raise RuntimeError("sandbox response must be a JSON object")
                return decoded
        except HTTPError as exc:
            detail = ""
            if getattr(exc, "fp", None) is not None:
                detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"sandbox execute failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"sandbox execute failed: {exc.reason}") from exc


def _resolve_cwd(task: dict[str, Any]) -> str:
    explicit = _sanitize_workspace_value(task.get("workspacePath"))
    if explicit:
        return explicit
    # Fall back to first allowed workspace prefix so sandbox policy is satisfied
    # when the task was created without a workspacePath (e.g. from mobile client).
    allowed = os.getenv("MVP_ALLOWED_WORKSPACE_PREFIXES", "").strip()
    first_prefix = next((_sanitize_workspace_value(p) for p in allowed.split(",") if _sanitize_workspace_value(p)), "")
    return first_prefix or os.getcwd()


def _sanitize_workspace_value(raw: Any) -> str:
    if raw is None:
        return ""
    text = str(raw).strip().strip('"').strip("'")
    if not text:
        return ""
    if text.lower() in {"none", "null", "undefined", "nil", "nan"}:
        return ""
    return text


def _read_timeout_seconds() -> int:
    raw = os.getenv("MVP_SANDBOX_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 30
    try:
        value = int(raw)
    except ValueError:
        return 30
    return value if value > 0 else 30


def _first_non_blank(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
