from __future__ import annotations

import pytest

from llm.llm_client import LLMClient, LLMClientError


def test_llm_client_reports_missing_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = LLMClient(response_provider=lambda backend, messages, model, temperature: "ok")  # noqa: ARG005
    with pytest.raises(LLMClientError):
        client.generate("hello")


def test_llm_client_strips_markdown_fence(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    client = LLMClient(response_provider=lambda backend, messages, model, temperature: "```json\n{\"k\":1}\n```")  # noqa: ARG005
    text = client.generate("return json")

    assert text == '{"k":1}'
