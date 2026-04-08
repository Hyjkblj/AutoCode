from __future__ import annotations

import pytest

from llm.llm_client import LLMClient, LLMClientError, strip_markdown_fence


def test_strip_markdown_fence_supports_fenced_and_plain_text() -> None:
    assert strip_markdown_fence("plain text") == "plain text"
    assert strip_markdown_fence("```json\n{\"intent\":\"deploy\"}\n```") == '{"intent":"deploy"}'


def test_llm_client_uses_documented_defaults(monkeypatch) -> None:
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)

    client = LLMClient()

    assert client.backend == "openai"
    assert client.model == "gpt-4.1-mini"
    assert client.temperature == 0.2


def test_openai_chat_returns_cleaned_text(monkeypatch) -> None:
    client = LLMClient(backend="openai", openai_api_key="dummy")
    monkeypatch.setattr(client, "_request_openai", lambda messages: "```python\nprint('ok')\n```")

    result = client.chat([{"role": "user", "content": "say ok"}])

    assert result == "print('ok')"


def test_chat_raises_when_required_key_missing() -> None:
    client = LLMClient(backend="claude", anthropic_api_key="")

    with pytest.raises(LLMClientError) as exc:
        client.chat([{"role": "user", "content": "hello"}])

    assert "ANTHROPIC_API_KEY missing" in str(exc.value)


def test_chat_includes_raw_error_details(monkeypatch) -> None:
    client = LLMClient(backend="openai", openai_api_key="dummy")

    def _boom(_messages):
        raise ValueError("upstream timeout")

    monkeypatch.setattr(client, "_request_openai", _boom)

    with pytest.raises(LLMClientError) as exc:
        client.chat([{"role": "user", "content": "hello"}])

    assert "upstream timeout" in str(exc.value)
