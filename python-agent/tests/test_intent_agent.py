from __future__ import annotations

from agents.intent_agent import IntentAgent
from llm.llm_client import LLMClient


def test_intent_agent_prefers_llm_result(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr(
        LLMClient,
        "chat",
        lambda self, messages: '{"intent":"deploy","confidence":0.93,"reason":"release request"}',
    )

    decision = IntentAgent().infer("please deploy this service to staging")

    assert decision.backend == "openai"
    assert decision.intent == "deploy"
    assert decision.confidence == 0.93
    assert decision.reason == "release request"


def test_intent_agent_reports_missing_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    decision = IntentAgent().infer("analyze this change")

    assert decision.backend == "claude"
    assert decision.intent == "llm_key_missing"
    assert "ANTHROPIC_API_KEY" in decision.reason


def test_intent_agent_falls_back_to_rule_when_llm_errors(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    decision = IntentAgent().infer("deploy this app")

    assert decision.intent == "deploy"
    assert decision.confidence > 0.5
    assert decision.reason.startswith("llm_fallback:")


def test_intent_agent_falls_back_to_code_change_for_flask_health_prompt(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    decision = IntentAgent().infer("给 Flask app 增加 /health 接口")

    assert decision.intent == "code_change"
    assert decision.confidence > 0.5
    assert decision.reason.startswith("llm_fallback:")


def test_intent_agent_discards_invalid_cached_response_and_recovers() -> None:
    responses = iter(
        [
            "not json",
            '{"intent":"deploy","confidence":0.91,"reason":"recovered"}',
        ]
    )
    client = LLMClient(
        response_provider=lambda backend, messages, model, temperature: next(responses),  # noqa: ARG005
        cache_enabled=True,
        cache_max_size=8,
        cache_ttl_seconds=60.0,
    )
    client.clear_cache(reset_stats=True)
    agent = IntentAgent(llm_client=client)

    first = agent.infer("deploy this app")
    second = agent.infer("deploy this app")

    assert first.intent == "deploy"
    assert first.reason.startswith("llm_fallback:")
    assert second.intent == "deploy"
    assert second.reason == "recovered"

