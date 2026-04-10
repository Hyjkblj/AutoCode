from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable
from urllib import request


class LLMClientError(RuntimeError):
    pass


ResponseProvider = Callable[[str, list[dict[str, str]], str, float], str]


@dataclass(frozen=True)
class LLMSettings:
    backend: str
    model: str
    temperature: float
    timeout_seconds: int


class LLMClient:
    def __init__(
        self,
        backend: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout_seconds: int | None = None,
        response_provider: ResponseProvider | None = None,
    ) -> None:
        resolved_backend = (backend or os.getenv("LLM_BACKEND", "openai")).strip().lower()
        if resolved_backend not in {"openai", "claude"}:
            resolved_backend = "openai"

        resolved_model = (model or os.getenv("LLM_MODEL", "gpt-4.1-mini")).strip() or "gpt-4.1-mini"
        resolved_temperature = _to_float(temperature if temperature is not None else os.getenv("LLM_TEMPERATURE"), 0.2)
        resolved_timeout = _to_int(timeout_seconds if timeout_seconds is not None else os.getenv("LLM_TIMEOUT_SECONDS"), 30)

        self.settings = LLMSettings(
            backend=resolved_backend,
            model=resolved_model,
            temperature=resolved_temperature,
            timeout_seconds=resolved_timeout,
        )
        self._response_provider = response_provider

    def is_configured(self) -> bool:
        return self.required_key_name() is None

    def required_key_name(self) -> str | None:
        if self.settings.backend == "openai":
            return None if os.getenv("OPENAI_API_KEY", "").strip() else "OPENAI_API_KEY"
        return None if os.getenv("ANTHROPIC_API_KEY", "").strip() else "ANTHROPIC_API_KEY"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages: list[dict[str, str]] = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": (prompt or "").strip()})
        return self.chat(messages)

    def chat(self, messages: list[dict[str, str]]) -> str:
        missing_key = self.required_key_name()
        if missing_key:
            raise LLMClientError(f"{missing_key} missing")
        if not messages:
            raise LLMClientError("messages must not be empty")

        try:
            if self._response_provider is not None:
                raw = self._response_provider(
                    self.settings.backend,
                    messages,
                    self.settings.model,
                    self.settings.temperature,
                )
            elif self.settings.backend == "openai":
                raw = self._chat_openai(messages)
            else:
                raw = self._chat_claude(messages)
        except Exception as exc:  # noqa: BLE001
            raise LLMClientError(str(exc)) from exc

        text = _strip_markdown_fence(str(raw))
        if not text.strip():
            raise LLMClientError("empty completion from llm")
        return text

    def _chat_openai(self, messages: list[dict[str, str]]) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        body = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
        }
        req = request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with request.urlopen(req, timeout=self.settings.timeout_seconds) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("invalid openai response: choices missing")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
            return "\n".join(part for part in parts if part.strip())
        raise LLMClientError("invalid openai response: message content missing")

    def _chat_claude(self, messages: list[dict[str, str]]) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        # Claude API expects a single system string plus user/assistant messages.
        system = ""
        converted: list[dict[str, str]] = []
        for item in messages:
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", ""))
            if role == "system":
                system = content if not system else f"{system}\n{content}"
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            converted.append({"role": role, "content": content})
        if not converted:
            converted.append({"role": "user", "content": ""})

        body: dict[str, object] = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "messages": converted,
            "max_tokens": 1200,
        }
        if system.strip():
            body["system"] = system

        req = request.Request(
            url="https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with request.urlopen(req, timeout=self.settings.timeout_seconds) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))

        content = payload.get("content")
        if not isinstance(content, list):
            raise LLMClientError("invalid claude response: content missing")

        texts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
        merged = "\n".join(part for part in texts if part.strip())
        if not merged.strip():
            raise LLMClientError("invalid claude response: text missing")
        return merged


def _to_float(raw: object, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _to_int(raw: object, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _strip_markdown_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if not lines:
        return cleaned
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
