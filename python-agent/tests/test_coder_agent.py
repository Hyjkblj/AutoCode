from __future__ import annotations

from typing import Any

from agents.coder_agent import CoderAgent
from agents.planner_agent import PlanResult
from llm.llm_client import LLMClient
from tools.file_tool import FileTool


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


def test_coder_agent_emits_file_patch_preview(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(LLMClient, "chat", lambda self, messages: "Updated docs\n")

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "README.md"
    target.write_text("TODO: update docs\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    task = {"workspacePath": str(workspace), "prompt": "fix readme text", "target_files": ["README.md"]}
    coder = CoderAgent(file_tool=FileTool([str(workspace)]))
    ok = coder.execute(
        task=task,
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is True
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "FILE_PATCH_PREVIEW"]
    assert events[1][1]["files"] == [{"path": "README.md", "changeType": "modify"}]
    assert "---" in events[1][1]["patch"]
    assert "+++" in events[1][1]["patch"]
    assert target.read_text(encoding="utf-8") == "Updated docs\n"
    assert task["generatedDiffs"]
    assert task["latestDiff"]


def test_coder_agent_reports_task_failed_when_write_is_out_of_bounds(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(LLMClient, "chat", lambda self, messages: "updated content\n")

    workspace = tmp_path / "workspace"
    denied_prefix = tmp_path / "allowed"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("before\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(denied_prefix)]))
    ok = coder.execute(
        task={"workspacePath": str(workspace), "prompt": "implement feature", "target_files": ["README.md"]},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is False
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "TASK_FAILED"]
    assert events[1][1]["reason"] == "path_not_allowed"
    assert events[1][1]["errorCode"] == "PATH_NOT_ALLOWED"


def test_coder_agent_continues_when_one_file_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(LLMClient, "chat", lambda self, messages: "new text\n")

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    good = workspace / "good.md"
    good.write_text("old\n", encoding="utf-8")

    blocked_root = tmp_path / "blocked"
    blocked_root.mkdir(parents=True, exist_ok=True)
    bad = blocked_root / "bad.md"
    bad.write_text("old\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    task = {
        "workspacePath": str(workspace),
        "prompt": "update both files",
        "target_files": [str(bad), "good.md"],
    }
    coder = CoderAgent(file_tool=FileTool([str(workspace)]))
    ok = coder.execute(
        task=task,
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is True
    event_types = [kind for kind, _ in events]
    assert event_types.count("TASK_FAILED") == 1
    assert event_types.count("FILE_PATCH_PREVIEW") == 1
    failed_payloads = [payload for kind, payload in events if kind == "TASK_FAILED"]
    assert failed_payloads[0]["errorCode"] == "PATH_NOT_ALLOWED"
    assert good.read_text(encoding="utf-8") == "new text\n"


def test_coder_agent_skips_write_when_no_substantial_change(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "README.md"
    target.write_text("same\n", encoding="utf-8")
    monkeypatch.setattr(LLMClient, "chat", lambda self, messages: "same\n")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    task = {"workspacePath": str(workspace), "prompt": "no change", "target_files": ["README.md"]}
    coder = CoderAgent(file_tool=FileTool([str(workspace)]))
    ok = coder.execute(
        task=task,
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is False
    assert [kind for kind, _ in events] == ["ASSISTANT_OUTPUT"]
    assert events[0][1]["message"].startswith("No substantial change")
    assert target.read_text(encoding="utf-8") == "same\n"
