from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from client.control_plane_client import ControlPlaneClient


class AgentOrchestrator(BaseAgent):
    def __init__(self, intent_agent: IntentAgent | None = None, planner_agent: PlannerAgent | None = None) -> None:
        super().__init__()
        self.intent_agent = intent_agent or IntentAgent()
        self.planner_agent = planner_agent or PlannerAgent()

    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        prompt = str(task.get("prompt", "")).strip()
        decision = self.intent_agent.infer(prompt)
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "IntentAgent",
                "message": "Intent analysis completed.",
                "backend": decision.backend,
                "intent": decision.intent,
                "confidence": decision.confidence,
                "reason": decision.reason,
            },
        )

        plan = self.planner_agent.build_plan(prompt=prompt, intent=decision)
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "PlannerAgent",
                "message": "Plan generated.",
                "planName": plan.plan_name,
                "steps": plan.steps,
            },
        )

        self.publish_event(
            task,
            client,
            "TASK_DONE",
            {
                "result": "planned",
                "planName": plan.plan_name,
                "steps": plan.steps,
            },
        )

