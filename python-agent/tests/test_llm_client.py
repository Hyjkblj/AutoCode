from __future__ import annotations

import json

import pytest

from llm.llm_client import LLMClient, LLMClientError


def test_llm_client_reports_missing_openai_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    config = {
        "provider": "openai",
        "api": {
            "auth_header": "Bearer ${OPENAI_API_KEY}",
        },
        "request": {"model": "gpt-4.1-mini"},
        "compat_env": {"LLM_BACKEND": "openai"},
    }
    config_path = tmp_path / "llm-profile.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    client = LLMClient(config_path=str(config_path), response_provider=lambda backend, messages, model, temperature: "ok")  # noqa: ARG005
    with pytest.raises(LLMClientError):
        client.generate("hello")


def test_llm_client_strips_markdown_fence(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    client = LLMClient(response_provider=lambda backend, messages, model, temperature: "```json\n{\"k\":1}\n```")  # noqa: ARG005
    text = client.generate("return json")

    assert text == '{"k":1}'


def test_llm_client_uses_profile_config_without_env_overrides(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ARK_API_KEY", "dummy")

    config = {
        "provider": "volcengine-ark",
        "api": {
            "base_url": "https://ark.example.com/api/v3",
            "chat_url": "https://ark.example.com/api/v3/chat/completions",
            "auth_header": "Bearer ${ARK_API_KEY}",
        },
        "request": {
            "model": "ep-test-model",
            "temperature": 0.35,
            "max_tokens": 9000,
        },
        "compat_env": {
            "LLM_BACKEND": "openai",
        },
    }
    config_path = tmp_path / "llm-profile.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    client = LLMClient(config_path=str(config_path), response_provider=lambda backend, messages, model, temperature: "ok")  # noqa: ARG005

    assert client.settings.backend == "openai"
    assert client.settings.model == "ep-test-model"
    assert client.settings.temperature == 0.35
    assert client.required_key_name() is None


def test_llm_client_profile_accepts_openai_key_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    config = {
        "provider": "volcengine-ark",
        "api": {
            "auth_header": "Bearer ${ARK_API_KEY}",
        },
        "request": {"model": "ep-test-model"},
        "compat_env": {"LLM_BACKEND": "openai"},
    }
    config_path = tmp_path / "llm-profile.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    client = LLMClient(config_path=str(config_path), response_provider=lambda backend, messages, model, temperature: "ok")  # noqa: ARG005

    assert client.required_key_name() is None


def test_llm_client_profile_reports_profile_key_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = {
        "provider": "volcengine-ark",
        "api": {
            "auth_header": "Bearer ${ARK_API_KEY}",
        },
        "request": {"model": "ep-test-model"},
        "compat_env": {"LLM_BACKEND": "openai"},
    }
    config_path = tmp_path / "llm-profile.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    client = LLMClient(config_path=str(config_path), response_provider=lambda backend, messages, model, temperature: "ok")  # noqa: ARG005

    assert client.required_key_name() == "ARK_API_KEY"


def test_llm_client_profile_with_embedded_auth_header_does_not_require_env_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    config = {
        "provider": "volcengine-ark",
        "api": {
            "auth_header": "Bearer f1050156-ed59-4d89-8fce-2fb5264e6ece",
        },
        "request": {"model": "ep-test-model"},
        "compat_env": {"LLM_BACKEND": "openai"},
    }
    config_path = tmp_path / "llm-profile.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    client = LLMClient(config_path=str(config_path), response_provider=lambda backend, messages, model, temperature: "ok")  # noqa: ARG005

    assert client.required_key_name() is None
    assert client.generate("ping") == "ok"


def test_llm_client_forwards_profile_openai_extra_request_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)

    config = {
        "provider": "volcengine-ark",
        "api": {
            "chat_url": "https://ark.example.com/api/v3/chat/completions",
            "auth_header": "Bearer static-token",
        },
        "request": {
            "model": "ep-test-model",
            "temperature": 0.2,
            "max_tokens": 8192,
            "stream": False,
            "service_tier": "auto",
            "reasoning_effort": "minimal",
            "top_p": 0.7,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "response_format": {"type": "text"},
            "parallel_tool_calls": False,
            "unexpected_option": "ignored",
        },
        "compat_env": {"LLM_BACKEND": "openai"},
    }
    config_path = tmp_path / "llm-profile.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
            return False

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def _fake_urlopen(req, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr("llm.llm_client.request.urlopen", _fake_urlopen)

    client = LLMClient(config_path=str(config_path))
    text = client.generate("hello")

    assert text == "ok"
    body = captured["body"]
    assert body["model"] == "ep-test-model"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 8192
    assert body["stream"] is False
    assert body["service_tier"] == "auto"
    assert body["reasoning_effort"] == "minimal"
    assert body["top_p"] == 0.7
    assert body["frequency_penalty"] == 0
    assert body["presence_penalty"] == 0
    assert body["response_format"] == {"type": "text"}
    assert body["parallel_tool_calls"] is False
    assert "unexpected_option" not in body
