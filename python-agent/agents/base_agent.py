from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from collections import defaultdict
from threading import Lock
from typing import Any
from uuid import uuid4

from client.control_plane_client import ControlPlaneClient
from utils.observability import enrich_payload, ensure_task_observability, record_event_publish


class BaseAgent(ABC):
    def __init__(self) -> None:
        self._seq_by_task: dict[str, int] = {}
        self._seq_lock = Lock()
        self._outbox_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._outbox_lock = Lock()

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
        ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
        self._flush_outbox(task, client)
        event = self._build_event(
            task=task,
            event_type=event_type,
            payload=enrich_payload(task, payload or {}),
            seq=self._next_seq(task_id),
        )
        self._enqueue_outbox(task_id, event)
        self._deliver_event(task, event, client)
        self._ack_outbox(task_id, str(event.get("eventId", "")).strip())

    def _next_seq(self, task_id: str) -> int:
        with self._seq_lock:
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

    def _flush_outbox(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        task_id = str(task.get("taskId", "")).strip()
        pending = self._pending_outbox(task_id)
        for event in pending:
            event_id = str(event.get("eventId", "")).strip()
            self._deliver_event(task, event, client)
            self._ack_outbox(task_id, event_id)

    def _deliver_event(self, task: dict[str, Any], event: dict[str, Any], client: ControlPlaneClient) -> None:
        task_id = str(task.get("taskId", "")).strip()
        attempts = 1
        publish_with_retry_result = getattr(client, "publish_event_with_retry_result", None)
        if callable(publish_with_retry_result):
            result = publish_with_retry_result(task_id, event)
            attempts = max(1, int(getattr(result, "attempts", 1)))
            record_event_publish(task, str(event.get("type", "")).strip(), attempts=attempts)
            return
        publish_with_retry = getattr(client, "publish_event_with_retry", None)
        if callable(publish_with_retry):
            publish_with_retry(task_id, event)
            record_event_publish(task, str(event.get("type", "")).strip(), attempts=attempts)
            return
        client.publish_event(task_id, event)
        record_event_publish(task, str(event.get("type", "")).strip(), attempts=attempts)

    def _enqueue_outbox(self, task_id: str, event: dict[str, Any]) -> None:
        with self._outbox_lock:
            self._outbox_by_task[task_id].append(dict(event))

    def _ack_outbox(self, task_id: str, event_id: str) -> None:
        with self._outbox_lock:
            pending = self._outbox_by_task.get(task_id, [])
            self._outbox_by_task[task_id] = [item for item in pending if str(item.get("eventId", "")).strip() != event_id]
            if not self._outbox_by_task[task_id]:
                self._outbox_by_task.pop(task_id, None)

    def _pending_outbox(self, task_id: str) -> list[dict[str, Any]]:
        with self._outbox_lock:
            return [dict(item) for item in self._outbox_by_task.get(task_id, [])]


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

