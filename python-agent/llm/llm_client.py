from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class LLMProfile:
    backend: str | None
    model: str | None
    temperature: float | None
    timeout_seconds: int | None
    openai_base_url: str | None
    openai_chat_url: str | None
    openai_auth_header: str | None
    openai_key_env: str | None
    openai_max_tokens: int | None
    openai_extra_request: dict[str, object]


_DEFAULT_PROFILE_NAME = "doubao-seed-2.0-code-high-perf.json"
_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
_ORIGINAL_URLOPEN = request.urlopen


class LLMClient:
    def __init__(
        self,
        backend: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout_seconds: int | None = None,
        response_provider: ResponseProvider | None = None,
        config_path: str | None = None,
    ) -> None:
        profile = _load_profile(config_path)

        resolved_backend = _pick_text(backend, os.getenv("LLM_BACKEND"), profile.backend, "openai").lower()
        if resolved_backend not in {"openai", "claude"}:
            resolved_backend = "openai"

        resolved_model = _pick_text(model, os.getenv("LLM_MODEL"), profile.model, "gpt-4.1-mini")
        temperature_raw: object = temperature if temperature is not None else _pick_object(
            os.getenv("LLM_TEMPERATURE"),
            profile.temperature,
        )
        timeout_raw: object = timeout_seconds if timeout_seconds is not None else _pick_object(
            os.getenv("LLM_TIMEOUT_SECONDS"),
            profile.timeout_seconds,
        )
        resolved_temperature = _to_float(temperature_raw, 0.2)
        resolved_timeout = _to_int(timeout_raw, 120)

        self.settings = LLMSettings(
            backend=resolved_backend,
            model=resolved_model,
            temperature=resolved_temperature,
            timeout_seconds=resolved_timeout,
        )

        self._openai_base_url = _pick_text(
            os.getenv("OPENAI_BASE_URL"),
            profile.openai_base_url,
            _DEFAULT_OPENAI_BASE_URL,
        ).rstrip("/")
        self._openai_chat_url = _pick_text(
            os.getenv("OPENAI_CHAT_URL"),
            profile.openai_chat_url,
            f"{self._openai_base_url}/v1/chat/completions",
        )
        self._openai_auth_header = _pick_text(profile.openai_auth_header, "Bearer ${OPENAI_API_KEY}")
        self._openai_key_candidates = _dedupe_non_empty(
            [
                _pick_text(profile.openai_key_env, _extract_env_var_name(self._openai_auth_header)),
                "OPENAI_API_KEY",
            ]
        )
        configured_openai_max = _to_int(profile.openai_max_tokens, 4096)
        self._openai_max_tokens = configured_openai_max if configured_openai_max >= 4096 else 4096
        self._openai_extra_request = dict(profile.openai_extra_request)

        import logging as _logging
        _logging.getLogger(__name__).info(
            "LLMClient initialized: backend=%s model=%s profile=%s base_url=%s",
            resolved_backend,
            resolved_model,
            _profile_marker(config_path),
            self._openai_base_url,
        )
        self._response_provider = response_provider

    def has_required_key(self) -> bool:
        return self.required_key_name() is None

    def is_configured(self) -> bool:
        return self.required_key_name() is None

    def required_key_name(self) -> str | None:
        if self.settings.backend == "openai":
            if _has_embedded_openai_auth(self._openai_auth_header):
                return None
            for key_name in self._openai_key_candidates:
                if os.getenv(key_name, "").strip():
                    return None
            return self._openai_key_candidates[0] if self._openai_key_candidates else "OPENAI_API_KEY"
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
        if self._response_provider is None:
            placeholder_key = self._placeholder_key_name()
            if placeholder_key is not None:
                raise LLMClientError(f"{placeholder_key} uses placeholder value")
            if _is_pytest_active() and request.urlopen is _ORIGINAL_URLOPEN:
                raise LLMClientError("live llm disabled during pytest")

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
        api_key = self._resolve_openai_api_key()
        auth_header = self._build_openai_auth_header(api_key)
        body = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "max_tokens": self._openai_max_tokens,
        }
        for key, value in self._openai_extra_request.items():
            if key in {"model", "messages", "temperature", "max_tokens"}:
                continue
            body[key] = value
        req = request.Request(
            url=self._openai_chat_url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": auth_header,
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
            "max_tokens": 8192,
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

    def _resolve_openai_api_key(self) -> str:
        for key_name in self._openai_key_candidates:
            value = os.getenv(key_name, "").strip()
            if value:
                return value
        return ""

    def _build_openai_auth_header(self, api_key: str) -> str:
        template = (self._openai_auth_header or "").strip()
        if not template:
            return f"Bearer {api_key}"
        if "${" in template:
            return re.sub(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", api_key, template)
        if "{key}" in template:
            return template.replace("{key}", api_key)
        if api_key and api_key not in template:
            return f"{template} {api_key}".strip()
        return template

    def _placeholder_key_name(self) -> str | None:
        if self.settings.backend == "openai":
            for key_name in self._openai_key_candidates:
                value = os.getenv(key_name, "").strip()
                if _looks_like_placeholder_secret(value):
                    return key_name
            return None
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        return "ANTHROPIC_API_KEY" if _looks_like_placeholder_secret(api_key) else None


def _load_profile(config_path: str | None) -> LLMProfile:
    path = _resolve_profile_path(config_path)
    if path is None:
        return LLMProfile(
            backend=None,
            model=None,
            temperature=None,
            timeout_seconds=None,
            openai_base_url=None,
            openai_chat_url=None,
            openai_auth_header=None,
            openai_key_env=None,
            openai_max_tokens=None,
            openai_extra_request={},
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return LLMProfile(
            backend=None,
            model=None,
            temperature=None,
            timeout_seconds=None,
            openai_base_url=None,
            openai_chat_url=None,
            openai_auth_header=None,
            openai_key_env=None,
            openai_max_tokens=None,
            openai_extra_request={},
        )

    if not isinstance(payload, dict):
        return LLMProfile(
            backend=None,
            model=None,
            temperature=None,
            timeout_seconds=None,
            openai_base_url=None,
            openai_chat_url=None,
            openai_auth_header=None,
            openai_key_env=None,
            openai_max_tokens=None,
            openai_extra_request={},
        )

    api = payload.get("api") if isinstance(payload.get("api"), dict) else {}
    request_cfg = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    compat_env = payload.get("compat_env") if isinstance(payload.get("compat_env"), dict) else {}

    backend = _as_text(compat_env.get("LLM_BACKEND"))
    if not backend:
        provider = _as_text(payload.get("provider")).lower()
        if "claude" in provider:
            backend = "claude"
        elif provider:
            backend = "openai"

    auth_header = _as_text(api.get("auth_header"))
    auth_env_name = _extract_env_var_name(auth_header)

    return LLMProfile(
        backend=backend or None,
        model=_pick_text(request_cfg.get("model"), compat_env.get("LLM_MODEL")) or None,
        temperature=_to_float_or_none(_pick_object(request_cfg.get("temperature"), compat_env.get("LLM_TEMPERATURE"))),
        timeout_seconds=_to_int_or_none(_pick_object(request_cfg.get("timeout_seconds"), compat_env.get("LLM_TIMEOUT_SECONDS"))),
        openai_base_url=_pick_text(api.get("base_url"), compat_env.get("OPENAI_BASE_URL")) or None,
        openai_chat_url=_pick_text(api.get("chat_url"), compat_env.get("OPENAI_CHAT_URL")) or None,
        openai_auth_header=auth_header or None,
        openai_key_env=auth_env_name or None,
        openai_max_tokens=_to_int_or_none(request_cfg.get("max_tokens")),
        openai_extra_request=_extract_openai_extra_request(request_cfg),
    )


def _resolve_profile_path(config_path: str | None) -> Path | None:
    base_dir = Path(__file__).resolve().parents[1]

    for raw in (
        config_path,
        os.getenv("LLM_CONFIG_PATH", ""),
        os.getenv("LLM_PROFILE", ""),
    ):
        candidate = _normalize_profile_candidate(raw, base_dir)
        if candidate is not None and candidate.exists():
            return candidate

    default_path = base_dir / "configs" / _DEFAULT_PROFILE_NAME
    if default_path.exists():
        return default_path
    return None


def _normalize_profile_candidate(raw: object, base_dir: Path) -> Path | None:
    text = _as_text(raw)
    if not text:
        return None
    candidate = Path(text)
    if not candidate.suffix:
        candidate = Path(f"{candidate}.json")
    if not candidate.is_absolute():
        direct = (base_dir / candidate).resolve()
        configs_path = (base_dir / "configs" / candidate.name).resolve()
        if direct.exists():
            return direct
        return configs_path
    return candidate


def _profile_marker(config_path: str | None) -> str:
    path = _resolve_profile_path(config_path)
    if path is None:
        return "(none)"
    return str(path)


def _extract_env_var_name(text: str) -> str:
    match = re.search(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text or "")
    if not match:
        return ""
    return match.group(1).strip()


def _has_embedded_openai_auth(auth_header: str) -> bool:
    text = (auth_header or "").strip()
    if not text:
        return False
    if "${" in text or "{key}" in text:
        return False
    lowered = text.lower()
    if lowered == "bearer":
        return False
    if lowered.startswith("bearer "):
        token = text.split(" ", 1)[1].strip()
        return bool(token)
    return True


def _extract_openai_extra_request(request_cfg: dict[str, object]) -> dict[str, object]:
    allowed_keys = (
        "stream",
        "service_tier",
        "reasoning_effort",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
        "response_format",
        "parallel_tool_calls",
    )
    output: dict[str, object] = {}
    for key in allowed_keys:
        if key in request_cfg:
            output[key] = request_cfg[key]
    return output


def _dedupe_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in values:
        normalized = (item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _as_text(raw: object) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _pick_object(*values: object) -> object | None:
    for item in values:
        if item is None:
            continue
        if isinstance(item, str) and not item.strip():
            continue
        return item
    return None


def _pick_text(*values: object) -> str:
    picked = _pick_object(*values)
    if picked is None:
        return ""
    return str(picked).strip()


def _to_float_or_none(raw: object) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


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


def _looks_like_placeholder_secret(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    placeholder_values = {
        "dummy",
        "dummy-key",
        "test",
        "test-key",
        "fake",
        "fake-key",
        "placeholder",
        "placeholder-key",
        "changeme",
        "your-api-key",
    }
    return normalized in placeholder_values or normalized.startswith("dummy-") or normalized.startswith("test-")


def _is_pytest_active() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST", "").strip())
