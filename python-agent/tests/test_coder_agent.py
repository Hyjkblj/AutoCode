from __future__ import annotations

from typing import Any

from agents.coder_agent import CoderAgent
from agents.planner_agent import PlanResult
from tools.file_tool import FileTool


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


def test_coder_agent_emits_file_patch_preview(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "README.md"
    target.write_text("TODO: update docs\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(workspace)]))
    ok = coder.execute(
        task={"workspacePath": str(workspace), "prompt": "fix readme text"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is True
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "FILE_PATCH_PREVIEW"]
    assert events[1][1]["files"] == [{"path": "README.md", "changeType": "modify"}]
    assert "---" in events[1][1]["patch"]
    assert "coder-agent-note" in target.read_text(encoding="utf-8")


def test_coder_agent_reports_task_failed_when_write_is_out_of_bounds(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    denied_prefix = tmp_path / "allowed"
    workspace.mkdir(parents=True, exist_ok=True)

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(denied_prefix)]))
    ok = coder.execute(
        task={"workspacePath": str(workspace), "prompt": "implement feature"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is False
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "TASK_FAILED"]
    assert events[1][1]["reason"] == "path_not_allowed"
