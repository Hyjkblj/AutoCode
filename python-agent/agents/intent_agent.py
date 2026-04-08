from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm.llm_client import LLMClient


_ALLOWED_INTENTS = {"code_change", "deploy", "test", "analyze"}
_INTENT_ALIASES = {
    "code": "code_change",
    "coding": "code_change",
    "refactor": "code_change",
    "analysis": "analyze",
}
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


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
        normalized = (prompt or "").strip().lower()
        backend = self.llm_client.backend

        if not self.llm_client.has_required_key():
            return IntentDecision(
                backend=backend,
                intent="llm_key_missing",
                confidence=0.0,
                reason=f"{self.llm_client.required_key_name()} missing",
            )

        try:
            response = self.llm_client.chat(_intent_messages(normalized))
            payload = _parse_json_object(response)
            intent = _normalize_intent(payload.get("intent"))
            confidence = _normalize_confidence(payload.get("confidence"), fallback=0.66)
            reason = str(payload.get("reason") or "llm_inference").strip() or "llm_inference"
            return IntentDecision(backend=backend, intent=intent, confidence=confidence, reason=reason)
        except Exception as exc:  # noqa: BLE001
            fallback_intent, fallback_confidence, fallback_reason = _heuristic_intent(normalized)
            return IntentDecision(
                backend=backend,
                intent=fallback_intent,
                confidence=fallback_confidence,
                reason=f"llm_fallback:{fallback_reason}; error={exc}",
            )


def _intent_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an intent classifier for a coding agent. "
                "Return strict JSON with keys: intent, confidence, reason. "
                "intent must be one of: code_change, deploy, test, analyze."
            ),
        },
        {
            "role": "user",
            "content": f"Prompt:\n{prompt}",
        },
    ]


def _heuristic_intent(normalized_prompt: str) -> tuple[str, float, str]:
    if any(word in normalized_prompt for word in ("deploy", "release", "publish")):
        return "deploy", 0.9, "deploy keywords"
    if any(word in normalized_prompt for word in ("test", "pytest", "mvn test")):
        return "test", 0.82, "test keywords"
    if any(word in normalized_prompt for word in ("fix", "refactor", "code", "implement")):
        return "code_change", 0.86, "coding keywords"
    return "analyze", 0.68, "default heuristic"


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
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in _ALLOWED_INTENTS:
        return normalized
    return _INTENT_ALIASES.get(normalized, "analyze")


def _normalize_confidence(value: object, fallback: float) -> float:
    try:
        confidence = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence

