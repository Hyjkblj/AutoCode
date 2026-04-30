from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm.llm_client import LLMClient


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_SUPPORTED_INTENTS = {"code_change", "deploy", "test", "analyze"}


@dataclass(frozen=True)
class IntentDecision:
    backend: str
    intent: str
    confidence: float
    reason: str


class IntentAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def infer(self, prompt: str) -> IntentDecision:
        backend = self.llm_client.settings.backend
        missing_key = self.llm_client.required_key_name()
        if missing_key:
            return IntentDecision(
                backend=backend,
                intent="llm_key_missing",
                confidence=0.0,
                reason=f"{missing_key} missing",
            )

        try:
            cache_cursor = self.llm_client.cache_event_cursor()
            payload = _parse_json_object(self.llm_client.chat(_intent_messages(prompt)))
            intent = _normalize_intent(payload.get("intent"))
            confidence = _normalize_confidence(payload.get("confidence"))
            reason = str(payload.get("reason") or "llm").strip() or "llm"
            return IntentDecision(backend=backend, intent=intent, confidence=confidence, reason=reason)
        except Exception as exc:  # noqa: BLE001
            self.llm_client.discard_cache_entries_since(cache_cursor, reason="invalid_intent_response")
            fallback = _heuristic_intent(prompt=prompt, backend=backend)
            return IntentDecision(
                backend=backend,
                intent=fallback.intent,
                confidence=fallback.confidence,
                reason=f"llm_fallback:{exc}",
            )


def _intent_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an intent classifier for software tasks. "
                "Return strict JSON with keys: intent, confidence, reason. "
                "intent must be one of: code_change, deploy, test, analyze."
            ),
        },
        {
            "role": "user",
            "content": (prompt or "").strip(),
        },
    ]


def _parse_json_object(raw: str) -> dict[str, object]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty intent response")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if match is None:
            raise ValueError(f"intent response is not valid JSON: {text}") from None
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError(f"intent response must be an object: {payload!r}")
    return payload


def _normalize_intent(value: object) -> str:
    intent = str(value or "").strip().lower()
    if intent not in _SUPPORTED_INTENTS:
        raise ValueError(f"unsupported intent from llm: {intent}")
    return intent


def _normalize_confidence(value: object) -> float:
    if value is None:
        return 0.75
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("intent confidence must be numeric") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("intent confidence must be within [0,1]")
    return confidence


def _heuristic_intent(prompt: str, backend: str) -> IntentDecision:
    normalized = (prompt or "").strip().lower()

    if any(
        word in normalized
        for word in (
            "deploy",
            "release",
            "publish",
            "部署",
            "发布",
            "上线",
            "投产",
        )
    ):
        return IntentDecision(backend=backend, intent="deploy", confidence=0.9, reason="deploy keywords")

    if any(
        word in normalized
        for word in (
            "test",
            "pytest",
            "mvn test",
            "测试",
            "验收",
            "验证",
            "回归",
        )
    ):
        return IntentDecision(backend=backend, intent="test", confidence=0.82, reason="test keywords")

    code_markers = (
        "fix",
        "refactor",
        "code",
        "implement",
        "flask",
        "fastapi",
        "route",
        "endpoint",
        "api",
        "controller",
        "service",
        "修复",
        "重构",
        "优化",
        "接口",
        "/health",
    )
    if any(word in normalized for word in code_markers):
        return IntentDecision(backend=backend, intent="code_change", confidence=0.86, reason="coding keywords")

    generation_markers = (
        "web",
        "html",
        "website",
        "page",
        "生成",
        "开发",
        "实现",
        "页面",
        "网页",
        "前端",
        "应用",
        "系统",
        "管理系统",
        "backend",
        "fullstack",
        "后端",
        "全栈",
    )
    if any(word in normalized for word in generation_markers):
        return IntentDecision(backend=backend, intent="code_change", confidence=0.88, reason="generation keywords")

    return IntentDecision(backend=backend, intent="analyze", confidence=0.68, reason="default heuristic")
