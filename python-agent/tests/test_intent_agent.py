from __future__ import annotations

from agents.intent_agent import IntentAgent


def test_intent_agent_detects_deploy(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    decision = IntentAgent().infer("please deploy this service to staging")

    assert decision.backend == "openai"
    assert decision.intent == "deploy"
    assert decision.confidence > 0.5


def test_intent_agent_reports_missing_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    decision = IntentAgent().infer("analyze this change")

    assert decision.backend == "claude"
    assert decision.intent == "llm_key_missing"
    assert "ANTHROPIC_API_KEY" in decision.reason

