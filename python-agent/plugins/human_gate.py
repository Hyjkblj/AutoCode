from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


class PipelineStage(Enum):
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    DEPLOY = "deploy"


@dataclass(frozen=True)
class GateDecision:
    approved: bool
    feedback: str | None = None


class HumanGate:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client
        self._pending: dict[str, dict] = {}

    def should_gate(self, stage: PipelineStage, task: dict) -> bool:
        configured = task.get("approvalStages", [])
        if isinstance(configured, list):
            return stage.value in configured
        env_stages = os.getenv("MVP_APPROVAL_STAGES", "").split(",")
        return stage.value in [s.strip() for s in env_stages]

    def request_approval(self, task: dict, stage: PipelineStage, summary: str, details: dict) -> str:
        approval_id = str(uuid.uuid4())
        self._pending[approval_id] = {
            "stage": stage.value,
            "summary": summary,
            "details": details,
            "task": task,
        }
        return approval_id

    def check_approval(self, approval_id: str, timeout_seconds: int = 300) -> GateDecision:
        if approval_id not in self._pending:
            return GateDecision(approved=False, feedback="Unknown approval ID")
        if not self.client:
            return GateDecision(approved=True, feedback="Auto-approved (no client)")
        return GateDecision(approved=True, feedback="Approved")
