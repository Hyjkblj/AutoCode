from __future__ import annotations

import json
import re
from dataclasses import dataclass

from agents.intent_agent import IntentDecision
from llm.llm_client import LLMClient
from utils.circuit_breaker import CircuitBreaker
from utils.observability import TaskObservability


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class PlanResult:
    plan_name: str
    steps: list[str]
    reason: str = ""


class PlannerAgent:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name="planner-llm")

    def build_plan(self, prompt: str, intent: IntentDecision) -> PlanResult:
        return self.build_plan_with_observability(prompt=prompt, intent=intent, observation=None)

    def build_plan_with_observability(
        self,
        *,
        prompt: str,
        intent: IntentDecision,
        observation: TaskObservability | None,
    ) -> PlanResult:
        if intent.intent == "llm_key_missing":
            return PlanResult(
                plan_name="blocked_missing_key",
                steps=["report missing LLM API key requirement", "stop execution until key is configured"],
                reason=intent.reason,
            )

        cache_cursor = self.llm_client.cache_event_cursor()
        try:
            response = self.circuit_breaker.call(lambda: self.llm_client.chat(_planner_messages(prompt, intent.intent)))
            payload = _parse_json_object(response)
            plan_name = _normalize_plan_name(payload.get("plan_name"), intent.intent)
            steps = _normalize_steps(payload.get("steps"))
            if not steps:
                raise ValueError("planner response steps must not be empty")
            if observation is not None:
                self.llm_client.record_cache_metrics(
                    observation,
                    stage="PlannerAgent",
                    backend=intent.backend,
                    since_sequence=cache_cursor,
                )
            return PlanResult(plan_name=plan_name, steps=steps, reason="llm")
        except Exception as exc:  # noqa: BLE001
            self.llm_client.discard_cache_entries_since(cache_cursor, reason="invalid_planner_response")
            if observation is not None:
                self.llm_client.record_cache_metrics(
                    observation,
                    stage="PlannerAgent",
                    backend=intent.backend,
                    since_sequence=cache_cursor,
                )
            fallback = _fallback_plan(intent.intent)
            return PlanResult(
                plan_name=fallback.plan_name,
                steps=fallback.steps,
                reason=f"llm_fallback:{exc}",
            )


def _planner_messages(prompt: str, intent: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a planning agent for software tasks. "
                "Return strict JSON with keys: plan_name, steps. "
                "steps must be a non-empty list of concise strings."
            ),
        },
        {
            "role": "user",
            "content": f"intent={intent}\nprompt={prompt}",
        },
    ]


def _fallback_plan(intent_name: str) -> PlanResult:
    if intent_name == "deploy":
        return PlanResult(
            plan_name="deploy_pipeline",
            steps=[
                "collect release context",
                "verify artifact and environment",
                "request approval if required",
                "execute deployment and report result",
            ],
        )
    if intent_name == "test":
        return PlanResult(
            plan_name="test_pipeline",
            steps=[
                "inspect test target",
                "run test command",
                "summarize failures and retries",
            ],
        )
    if intent_name == "code_change":
        return PlanResult(
            plan_name="code_change_pipeline",
            steps=[
                "read relevant files",
                "propose minimal patch",
                "run validation command",
                "report change summary",
            ],
        )
    return PlanResult(
        plan_name="analysis_pipeline",
        steps=[
            "clarify task intent",
            "gather context",
            "produce structured next actions",
        ],
    )


def _parse_json_object(raw: str) -> dict[str, object]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty planner response")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if match is None:
            raise ValueError(f"planner response is not valid JSON: {text}") from None
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError(f"planner response must be an object: {payload!r}")
    return payload


def _normalize_plan_name(value: object, intent_name: str) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if raw:
        return raw
    return _fallback_plan(intent_name).plan_name


def _normalize_steps(value: object) -> list[str]:
    if isinstance(value, list):
        steps = [str(item).strip() for item in value if str(item).strip()]
        return steps
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []

