from __future__ import annotations

from typing import Any

from orchestrator.agent_orchestrator import AgentOrchestrator


class _FakeClient:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append((task_id, event))
        return {"eventId": event.get("eventId")}


def test_orchestrator_emits_intent_and_planner_events(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_100",
        "assistant": "ai-agent",
        "sessionKey": "sess_100",
        "prompt": "please deploy this change",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "TASK_DONE"]
    assert client.events[0][1]["payload"]["stage"] == "IntentAgent"
    assert client.events[1][1]["payload"]["stage"] == "PlannerAgent"

