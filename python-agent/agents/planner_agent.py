from __future__ import annotations

from dataclasses import dataclass

from agents.intent_agent import IntentDecision


@dataclass(frozen=True)
class PlanResult:
    plan_name: str
    steps: list[str]


class PlannerAgent:
    def build_plan(self, prompt: str, intent: IntentDecision) -> PlanResult:
        if intent.intent == "deploy":
            return PlanResult(
                plan_name="deploy_pipeline",
                steps=[
                    "collect release context",
                    "verify artifact and environment",
                    "request approval if required",
                    "execute deployment and report result",
                ],
            )
        if intent.intent == "test":
            return PlanResult(
                plan_name="test_pipeline",
                steps=[
                    "inspect test target",
                    "run test command",
                    "summarize failures and retries",
                ],
            )
        if intent.intent == "code_change":
            return PlanResult(
                plan_name="code_change_pipeline",
                steps=[
                    "read relevant files",
                    "propose minimal patch",
                    "run validation command",
                    "report change summary",
                ],
            )
        if intent.intent == "llm_key_missing":
            return PlanResult(
                plan_name="blocked_missing_key",
                steps=["report missing LLM API key requirement", "stop execution until key is configured"],
            )
        return PlanResult(
            plan_name="analysis_pipeline",
            steps=[
                "clarify task intent",
                "gather context",
                "produce structured next actions",
            ],
        )

