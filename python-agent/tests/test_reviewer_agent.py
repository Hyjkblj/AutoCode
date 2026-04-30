from __future__ import annotations

from typing import Any

from agents.planner_agent import PlanResult
from agents.reviewer_agent import ReviewerAgent
from llm.llm_client import LLMClient
from tools.search_tool import SearchTool


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


def test_reviewer_agent_maps_high_risk_to_reject(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(
        LLMClient,
        "chat",
        lambda self, messages: '{"risk_level":"high","issues":["unsafe shell"],"summary":"dangerous command"}',
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = ReviewerAgent().review(
        task={"workspacePath": str(workspace), "taskId": "task_301", "latestDiff": "--- a/x\n+++ b/x\n+danger\n"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert result.approved is False
    assert result.risk_level == "high"
    assert result.issues == ["unsafe shell"]
    assert events[0][0] == "ASSISTANT_OUTPUT"
    assert events[0][1]["riskLevel"] == "high"


def test_reviewer_agent_maps_medium_risk_to_approve(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(
        LLMClient,
        "chat",
        lambda self, messages: '{"risk_level":"medium","issues":["missing test"],"summary":"looks okay"}',
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = ReviewerAgent().review(
        task={"workspacePath": str(workspace), "taskId": "task_302", "latestDiff": "--- a/y\n+++ b/y\n+line\n"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert result.approved is True
    assert result.risk_level == "medium"
    assert events[0][1]["approved"] is True


def test_reviewer_agent_passes_low_risk_when_diff_empty(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = ReviewerAgent().review(
        task={"workspacePath": str(workspace), "taskId": "task_303", "latestDiff": ""},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert result.approved is True
    assert result.risk_level == "low"
    assert result.issues == []
    assert events[0][1]["summary"].startswith("No diff provided")


def test_reviewer_agent_falls_back_to_blocker_scan_when_llm_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "unsafe.md").write_text("REVIEW_BLOCKER: risky\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = ReviewerAgent().review(
        task={"workspacePath": str(workspace), "taskId": "task_304", "latestDiff": "--- a/z\n+++ b/z\n+line\n"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert result.approved is False
    assert result.risk_level == "high"
    assert result.issues == ["unsafe.md"]
    assert events[0][1]["approved"] is False


def test_reviewer_agent_discards_invalid_cached_response_and_recovers(tmp_path) -> None:
    responses = iter(
        [
            "not json",
            '{"risk_level":"low","issues":[],"summary":"recovered"}',
        ]
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    client = LLMClient(
        response_provider=lambda backend, messages, model, temperature: next(responses),  # noqa: ARG005
        cache_enabled=True,
        cache_max_size=8,
        cache_ttl_seconds=60.0,
    )
    client.clear_cache(reset_stats=True)
    agent = ReviewerAgent(llm_client=client, search_tool=SearchTool())

    first = agent.review(
        task={"workspacePath": str(workspace), "taskId": "task_305", "latestDiff": "--- a/z\n+++ b/z\n+line\n"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )
    second = agent.review(
        task={"workspacePath": str(workspace), "taskId": "task_306", "latestDiff": "--- a/z\n+++ b/z\n+line\n"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=publish,
    )

    assert first.summary.startswith("LLM unavailable; fallback review passed")
    assert second.summary == "recovered"
