from __future__ import annotations

from typing import Any

from agents.planner_agent import PlanResult
from agents.reviewer_agent import ReviewerAgent


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


def test_reviewer_agent_passes_without_blocker(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("normal content\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = ReviewerAgent().review(
        task={"workspacePath": str(workspace), "taskId": "task_301"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert result.approved is True
    assert result.issues == []
    assert events[0][0] == "ASSISTANT_OUTPUT"
    assert events[0][1]["stage"] == "ReviewerAgent"


def test_reviewer_agent_rejects_when_blocker_found(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "unsafe.md").write_text("REVIEW_BLOCKER: risky\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = ReviewerAgent().review(
        task={"workspacePath": str(workspace), "taskId": "task_302"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert result.approved is False
    assert result.issues == ["unsafe.md"]
    assert events[0][1]["approved"] is False

