from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentDecision:
    backend: str
    intent: str
    confidence: float
    reason: str


class IntentAgent:
    def infer(self, prompt: str) -> IntentDecision:
        normalized = (prompt or "").strip().lower()
        backend = (os.getenv("LLM_BACKEND", "openai").strip() or "openai").lower()
        backend = backend if backend in {"openai", "claude"} else "openai"

        if backend == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
            return IntentDecision(backend=backend, intent="llm_key_missing", confidence=0.0, reason="OPENAI_API_KEY missing")
        if backend == "claude" and not os.getenv("ANTHROPIC_API_KEY", "").strip():
            return IntentDecision(
                backend=backend,
                intent="llm_key_missing",
                confidence=0.0,
                reason="ANTHROPIC_API_KEY missing",
            )

        if any(word in normalized for word in ("deploy", "release", "publish")):
            return IntentDecision(backend=backend, intent="deploy", confidence=0.9, reason="deploy keywords")
        if any(word in normalized for word in ("test", "pytest", "mvn test")):
            return IntentDecision(backend=backend, intent="test", confidence=0.82, reason="test keywords")
        if any(word in normalized for word in ("web", "html", "website", "page")):
            return IntentDecision(backend=backend, intent="code_change", confidence=0.88, reason="web generation keywords")
        if any(word in normalized for word in ("fix", "refactor", "code", "implement")):
            return IntentDecision(backend=backend, intent="code_change", confidence=0.86, reason="coding keywords")
        return IntentDecision(backend=backend, intent="analyze", confidence=0.68, reason="default heuristic")

