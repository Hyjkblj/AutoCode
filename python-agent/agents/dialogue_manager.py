from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClarificationQuestion:
    question: str
    options: list[str] | None
    context: str
    stage: str


class DialogueManager:
    _SYSTEM_PROMPT = (
        "You are a requirements clarification assistant. "
        "Given a user request and the current stage, determine if the request is clear enough to proceed. "
        "Respond with JSON: {\"needs_clarification\": bool, \"question\": str?, \"options\": [str]?, \"context\": str?, \"stage\": str?}"
    )

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client
        self._turns: list[dict[str, str]] = []

    def needs_clarification(self, prompt: str, stage: str, context: dict) -> ClarificationQuestion | None:
        if not self.llm_client:
            return None
        user_msg = f"Stage: {stage}\nContext: {json.dumps(context, ensure_ascii=False)[:500]}\nUser request: {prompt}"
        self._turns.append({"role": "user", "content": prompt})
        try:
            raw = self.llm_client.generate(user_msg, system_prompt=self._SYSTEM_PROMPT)
            data = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return None
        if not data.get("needs_clarification"):
            return None
        return ClarificationQuestion(
            question=data.get("question", "Could you clarify your request?"),
            options=data.get("options"),
            context=data.get("context", ""),
            stage=data.get("stage", stage),
        )

    def incorporate_clarification(self, original_prompt: str, answer: str) -> str:
        self._turns.append({"role": "user", "content": answer})
        return f"{original_prompt} (补充说明: {answer})"

    def summarize_context(self, *, max_turns: int = 10) -> str:
        if not self._turns:
            return ""
        recent = self._turns[-max_turns:]
        return "\n".join(f"{t['role']}: {t['content']}" for t in recent)
