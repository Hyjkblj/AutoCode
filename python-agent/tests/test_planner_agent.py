from __future__ import annotations

from agents.intent_agent import IntentDecision
from agents.planner_agent import PlannerAgent
from llm.llm_client import LLMClient


def test_planner_agent_generates_dynamic_steps_from_llm(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(
        LLMClient,
        "chat",
        lambda self, messages: '{"plan_name":"deploy_dynamic","steps":["collect context","deploy","report"]}',
    )

    planner = PlannerAgent()
    intent = IntentDecision(backend="openai", intent="deploy", confidence=0.9, reason="deploy keywords")

    plan = planner.build_plan("deploy app", intent)

    assert plan.plan_name == "deploy_dynamic"
    assert plan.steps == ["collect context", "deploy", "report"]
    assert plan.reason == "llm"


def test_planner_agent_handles_missing_key() -> None:
    planner = PlannerAgent()
    intent = IntentDecision(backend="claude", intent="llm_key_missing", confidence=0.0, reason="missing")

    plan = planner.build_plan("anything", intent)

    assert plan.plan_name == "blocked_missing_key"
    assert plan.steps[0].startswith("report missing LLM API key")
    assert plan.reason == "missing"


def test_planner_agent_falls_back_when_llm_fails(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("planner llm failed")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    planner = PlannerAgent()
    intent = IntentDecision(backend="openai", intent="deploy", confidence=0.9, reason="deploy keywords")

    plan = planner.build_plan("deploy app", intent)

    assert plan.plan_name == "deploy_pipeline"
    assert "execute deployment and report result" in plan.steps
    assert plan.reason.startswith("llm_fallback:")

