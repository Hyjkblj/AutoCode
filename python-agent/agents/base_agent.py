from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from client.control_plane_client import ControlPlaneClient


class BaseAgent(ABC):
    def __init__(self) -> None:
        self._seq_by_task: dict[str, int] = {}

    @abstractmethod
    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        raise NotImplementedError

    def publish_event(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        event_type: str,
        payload: dict[str, Any] | None,
    ) -> None:
        task_id = str(task.get("taskId", "")).strip()
        if not task_id:
            raise ValueError("task.taskId is required")
        event = self._build_event(task=task, event_type=event_type, payload=payload or {}, seq=self._next_seq(task_id))
        client.publish_event(task_id, event)

    def _next_seq(self, task_id: str) -> int:
        current = self._seq_by_task.get(task_id, 0)
        self._seq_by_task[task_id] = current + 1
        return current

    @staticmethod
    def _build_event(task: dict[str, Any], event_type: str, payload: dict[str, Any], seq: int) -> dict[str, Any]:
        task_id = str(task.get("taskId", "")).strip()
        session_id = _first_non_blank(task.get("sessionId"), task.get("sessionKey"))
        event = {
            "eventId": "evt_" + uuid4().hex,
            "eventVersion": 1,
            "taskId": task_id,
            "assistant": _first_non_blank(task.get("assistant"), "ai-agent"),
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": max(seq, 0),
            "payload": payload,
        }
        if session_id:
            event["sessionId"] = session_id
        return event


class DefaultAiAgent(BaseAgent):
    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        prompt = str(task.get("prompt", "")).strip()
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "message": "AI agent accepted task, planning next steps.",
                "prompt": prompt,
            },
        )
        self.publish_event(
            task,
            client,
            "TASK_DONE",
            {
                "result": "accepted_for_ai_pipeline",
            },
        )


def _first_non_blank(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None

