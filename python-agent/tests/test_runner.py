from __future__ import annotations

from typing import Any

from agents.base_agent import DefaultAiAgent
from runner import AgentRunner, RunnerConfig


class _FakeClient:
    def __init__(self, tasks: list[dict[str, Any]]) -> None:
        self.tasks = list(tasks)
        self.register_calls: list[tuple[str, str | None]] = []
        self.heartbeat_calls: list[str] = []
        self.poll_calls: list[tuple[str, str]] = []
        self.events: list[tuple[str, dict[str, Any]]] = []

    def register(self, node_id: str, capabilities: str | None = None) -> dict[str, Any]:
        self.register_calls.append((node_id, capabilities))
        return {"nodeId": node_id}

    def heartbeat(self, node_id: str) -> dict[str, Any]:
        self.heartbeat_calls.append(node_id)
        return {"nodeId": node_id}

    def poll_next_task(self, node_id: str, profile: str = "ai-agent") -> dict[str, Any] | None:
        self.poll_calls.append((node_id, profile))
        return self.tasks.pop(0) if self.tasks else None

    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append((task_id, event))
        return {"eventId": event.get("eventId")}


def test_runner_registers_polls_and_dispatches() -> None:
    task = {"taskId": "task_1", "assistant": "ai-agent", "sessionKey": "sess_1", "prompt": "hello"}
    client = _FakeClient([task])
    config = RunnerConfig(
        base_url="http://localhost:8048",
        node_id="node-ai-1",
        agent_token="token",
        agent_profile="ai-agent",
        poll_interval_ms=1500,
        heartbeat_interval_ms=10000,
        capabilities="ai-agent,events,approval,profile:ai-agent",
    )
    runner = AgentRunner(client=client, config=config, agent=DefaultAiAgent())

    handled = runner.tick(now_ms=0)

    assert handled is True
    assert client.register_calls == [("node-ai-1", "ai-agent,events,approval,profile:ai-agent")]
    assert client.poll_calls == [("node-ai-1", "ai-agent")]
    assert [evt["type"] for _, evt in client.events] == ["ASSISTANT_OUTPUT", "TASK_DONE"]


def test_runner_sends_heartbeat_by_interval() -> None:
    client = _FakeClient([])
    config = RunnerConfig(
        base_url="http://localhost:8048",
        node_id="node-ai-1",
        agent_token="token",
        heartbeat_interval_ms=5000,
    )
    runner = AgentRunner(client=client, config=config, agent=DefaultAiAgent())

    assert runner.tick(now_ms=0) is False
    assert runner.tick(now_ms=6000) is False
    assert client.heartbeat_calls == ["node-ai-1"]

