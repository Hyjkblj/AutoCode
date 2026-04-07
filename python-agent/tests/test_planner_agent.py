from __future__ import annotations

from agents.intent_agent import IntentDecision
from agents.planner_agent import PlannerAgent


def test_planner_agent_generates_deploy_steps() -> None:
    planner = PlannerAgent()
    intent = IntentDecision(backend="openai", intent="deploy", confidence=0.9, reason="deploy keywords")

    plan = planner.build_plan("deploy app", intent)

    assert plan.plan_name == "deploy_pipeline"
    assert "execute deployment and report result" in plan.steps


def test_planner_agent_handles_missing_key() -> None:
    planner = PlannerAgent()
    intent = IntentDecision(backend="claude", intent="llm_key_missing", confidence=0.0, reason="missing")

    plan = planner.build_plan("anything", intent)

    assert plan.plan_name == "blocked_missing_key"
    assert plan.steps[0].startswith("report missing LLM API key")

