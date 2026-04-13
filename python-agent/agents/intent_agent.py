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

        has_openai_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
        has_ark_key = bool(os.getenv("ARK_API_KEY", "").strip())
        if backend == "openai" and not (has_openai_key or has_ark_key):
            return IntentDecision(backend=backend, intent="llm_key_missing", confidence=0.0, reason="OPENAI_API_KEY missing")
        if backend == "claude" and not os.getenv("ANTHROPIC_API_KEY", "").strip():
            return IntentDecision(
                backend=backend,
                intent="llm_key_missing",
                confidence=0.0,
                reason="ANTHROPIC_API_KEY missing",
            )

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
        if any(
            word in normalized
            for word in (
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
                "计算器",
                "天气",
                "图书",
                "管理系统",
            )
        ):
            return IntentDecision(backend=backend, intent="code_change", confidence=0.88, reason="generation keywords")
        if any(word in normalized for word in ("fix", "refactor", "code", "implement", "修复", "重构", "优化")):
            return IntentDecision(backend=backend, intent="code_change", confidence=0.86, reason="coding keywords")
        return IntentDecision(backend=backend, intent="analyze", confidence=0.68, reason="default heuristic")

