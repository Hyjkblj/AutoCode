from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import error, request


_FENCED_BLOCK_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*(.*?)\s*```$", re.DOTALL)


class LLMClientError(RuntimeError):
    """Raised when an LLM request cannot be completed or parsed."""


def strip_markdown_fence(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""
    match = _FENCED_BLOCK_RE.match(normalized)
    if match:
        return match.group(1).strip()
    return normalized


class LLMClient:
    def __init__(
        self,
        *,
        backend: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        backend_env = backend if backend is not None else os.getenv("LLM_BACKEND", "openai")
        normalized_backend = (backend_env or "openai").strip().lower()
        self.backend = normalized_backend if normalized_backend in {"openai", "claude"} else "openai"

        model_env = model if model is not None else os.getenv("LLM_MODEL", "gpt-4.1-mini")
        self.model = (model_env or "gpt-4.1-mini").strip() or "gpt-4.1-mini"

        temperature_raw: object
        if temperature is not None:
            temperature_raw = temperature
        else:
            temperature_raw = os.getenv("LLM_TEMPERATURE", "0.2")
        self.temperature = _parse_temperature(temperature_raw, fallback=0.2)
        self.timeout_seconds = timeout_seconds

        self.openai_api_key = (openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY", "")).strip()
        self.anthropic_api_key = (
            anthropic_api_key if anthropic_api_key is not None else os.getenv("ANTHROPIC_API_KEY", "")
        ).strip()

    def required_key_name(self) -> str:
        return "OPENAI_API_KEY" if self.backend == "openai" else "ANTHROPIC_API_KEY"

    def has_required_key(self) -> bool:
        if self.backend == "openai":
            return bool(self.openai_api_key)
        return bool(self.anthropic_api_key)

    def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.has_required_key():
            raise LLMClientError(f"{self.required_key_name()} missing")

        normalized_messages = _normalize_messages(messages)
        try:
            if self.backend == "claude":
                content = self._request_claude(normalized_messages)
            else:
                content = self._request_openai(normalized_messages)
        except LLMClientError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMClientError(f"{self.backend} call failed: {exc}") from exc
        return strip_markdown_fence(content)

    def _request_openai(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
        }
        data = self._post_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
            payload,
            provider="openai",
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError(f"openai response missing choices: {data}")
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMClientError(f"openai response choice is invalid: {data}")
        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMClientError(f"openai response missing message: {data}")
        content = message.get("content")
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    chunks.append(item["text"])
            content = "\n".join(chunks)
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError(f"openai response missing message.content: {data}")
        return content

    def _request_claude(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": 1024,
            "messages": messages,
        }
        data = self._post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": self.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload,
            provider="claude",
        )
        blocks = data.get("content")
        if not isinstance(blocks, list) or not blocks:
            raise LLMClientError(f"claude response missing content blocks: {data}")
        chunks: list[str] = []
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                chunks.append(block["text"])
        content = "\n".join(chunks).strip()
        if not content:
            raise LLMClientError(f"claude response missing text block: {data}")
        return content

    def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any], *, provider: str) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"{provider} API error {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise LLMClientError(f"{provider} network error: {exc.reason}") from exc
        except Exception as exc:  # noqa: BLE001
            raise LLMClientError(f"{provider} request failed: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"{provider} response is not valid JSON: {raw}") from exc
        if not isinstance(data, dict):
            raise LLMClientError(f"{provider} response must be an object: {data!r}")
        return data


def _parse_temperature(value: object, *, fallback: float) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if parsed < 0:
        return 0.0
    if parsed > 2:
        return 2.0
    return parsed


def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"system", "user", "assistant"}:
            continue
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    if not normalized:
        raise LLMClientError("messages must contain at least one valid role/content item")
    return normalized
