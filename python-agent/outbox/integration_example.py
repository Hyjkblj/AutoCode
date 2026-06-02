"""
Integration example showing how to use RedisOutbox with BaseAgent.

This example demonstrates how to integrate the Redis-based persistent outbox
with the existing BaseAgent architecture for reliable event delivery.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

from agents.base_agent import BaseAgent
from client.control_plane_client import ControlPlaneClient
from outbox.redis_outbox import RedisOutbox
from utils.observability import enrich_payload, ensure_task_observability, record_event_publish


class PersistentBaseAgent(BaseAgent):
    """
    Enhanced BaseAgent with Redis-based persistent outbox.
    
    This agent uses RedisOutbox for reliable event persistence,
    ensuring events survive system restarts and failures.
    """
    
    def __init__(self, outbox: RedisOutbox | None = None) -> None:
        super().__init__()
        self.outbox = outbox or RedisOutbox()
    
    def publish_event(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        event_type: str,
        payload: dict[str, Any] | None,
    ) -> None:
        """
        Publish event with persistent outbox pattern.
        
        This method implements the outbox pattern:
        1. Build and validate event
        2. Persist event to Redis outbox BEFORE delivery attempt
        3. Attempt delivery to Control Plane
        4. Acknowledge event in outbox on successful delivery
        """
        task_id = str(task.get("taskId", "")).strip()
        if not task_id:
            raise ValueError("task.taskId is required")
        
        ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
        
        # Recover any pending events first
        self._recover_pending_events(task, client)
        
        # Build event with next sequence number
        seq = self.outbox.get_next_sequence(task_id)
        event = self._build_event(
            task=task,
            event_type=event_type,
            payload=enrich_payload(task, payload or {}),
            seq=seq,
        )
        
        # CRITICAL: Persist event BEFORE delivery attempt (Requirement 2.1)
        self.outbox.store_event(task_id, event)
        
        # Attempt delivery
        try:
            self._deliver_event(task, event, client)
            # On successful delivery, acknowledge in outbox
            self.outbox.acknowledge_event(task_id, event["eventId"])
        except Exception:
            # Event remains in outbox for retry on next publish_event call
            # or during recovery after restart
            raise
    
    def _recover_pending_events(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        """
        Recover and redeliver pending events from outbox.
        
        This method is called at the start of each publish_event to ensure
        any previously failed deliveries are retried.
        """
        task_id = str(task.get("taskId", "")).strip()
        pending_events = self.outbox.get_pending_events(task_id)
        
        for event in pending_events:
            event_id = event.get("eventId", "")
            try:
                self._deliver_event(task, event, client)
                # On successful delivery, acknowledge in outbox
                self.outbox.acknowledge_event(task_id, event_id)
            except Exception:
                # Keep event in outbox for next retry
                continue
    
    def recover_all_pending_events(self, client: ControlPlaneClient) -> dict[str, int]:
        """
        Recover all pending events across all tasks.
        
        This method should be called during agent startup to recover
        events that were pending when the agent last shut down.
        
        Returns:
            Dictionary mapping task_id to number of events recovered
        """
        recovery_stats = {}
        pending_task_ids = self.outbox.get_all_pending_tasks()
        
        for task_id in pending_task_ids:
            pending_events = self.outbox.get_pending_events(task_id)
            recovered_count = 0
            
            # Create minimal task context for recovery
            task = {"taskId": task_id}
            
            for event in pending_events:
                event_id = event.get("eventId", "")
                try:
                    self._deliver_event(task, event, client)
                    self.outbox.acknowledge_event(task_id, event_id)
                    recovered_count += 1
                except Exception:
                    # Keep event in outbox for next retry
                    continue
            
            recovery_stats[task_id] = recovered_count
        
        return recovery_stats
    
    def cleanup_completed_task(self, task_id: str) -> None:
        """
        Clean up outbox data for a completed task.
        
        This should be called when a task is completed or cancelled
        to free up outbox storage.
        """
        self.outbox.cleanup_task(task_id)


class ExampleAgent(PersistentBaseAgent):
    """Example agent demonstrating persistent outbox usage."""
    
    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        """Handle a task with reliable event publishing."""
        prompt = str(task.get("prompt", "")).strip()
        
        # Publish task started event - will be persisted before delivery
        self.publish_event(
            task,
            client,
            "TASK_STARTED",
            {
                "message": "Task started with persistent outbox",
                "prompt": prompt,
            },
        )
        
        # Simulate some work
        import time
        time.sleep(0.1)
        
        # Publish progress event
        self.publish_event(
            task,
            client,
            "TASK_PROGRESS",
            {
                "message": "Task processing in progress",
                "progress": 50,
            },
        )
        
        # Publish completion event
        self.publish_event(
            task,
            client,
            "TASK_DONE",
            {
                "result": "completed_with_persistent_outbox",
                "message": "Task completed successfully",
            },
        )
        
        # Clean up outbox data for completed task
        task_id = str(task.get("taskId", "")).strip()
        self.cleanup_completed_task(task_id)


def example_usage():
    """Example of how to use the persistent outbox agent."""
    
    # Create Redis outbox (will fall back to memory if Redis unavailable)
    outbox = RedisOutbox(
        backend="redis",  # or "memory" for testing
        namespace="example:outbox",
        ttl_seconds=3600  # 1 hour TTL
    )
    
    # Create agent with persistent outbox
    agent = ExampleAgent(outbox=outbox)
    
    # Create mock client (in real usage, this would be a real ControlPlaneClient)
    class MockClient:
        def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
            print(f"Publishing event {event['eventId']} for task {task_id}")
            return {"ok": True}
    
    client = MockClient()
    
    # Example task
    task = {
        "taskId": "task_example_123",
        "prompt": "Generate a simple web page",
        "sessionId": "session_456"
    }
    
    # Handle task - events will be persisted before delivery
    try:
        agent.handle_task(task, client)
        print("Task completed successfully")
    except Exception as e:
        print(f"Task failed: {e}")
        # Events remain in outbox for recovery
        
        # Show pending events
        pending = outbox.get_pending_events(task["taskId"])
        print(f"Pending events: {len(pending)}")
        for event in pending:
            print(f"  - {event['type']}: {event['eventId']}")


def recovery_example():
    """Example of event recovery after agent restart."""
    
    # Create outbox (simulating agent restart)
    outbox = RedisOutbox(backend="memory", namespace="recovery:example")
    
    # Simulate some events that were pending before restart
    task_id = "task_recovery_123"
    
    # These would normally be in Redis from before the restart
    event1 = {
        "eventId": f"evt_{uuid4().hex}",
        "eventVersion": 1,
        "taskId": task_id,
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started before restart"}
    }
    
    event2 = {
        "eventId": f"evt_{uuid4().hex}",
        "eventVersion": 1,
        "taskId": task_id,
        "assistant": "ai-agent",
        "type": "TASK_PROGRESS",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 1,
        "payload": {"message": "Task progress before restart", "progress": 25}
    }
    
    # Store events (simulating they were persisted before restart)
    outbox.store_event(task_id, event1)
    outbox.store_event(task_id, event2)
    
    # Create agent and recover events
    agent = ExampleAgent(outbox=outbox)
    
    class MockClient:
        def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
            print(f"Recovering event {event['eventId']}: {event['type']}")
            return {"ok": True}
    
    client = MockClient()
    
    # Recover all pending events
    recovery_stats = agent.recover_all_pending_events(client)
    print(f"Recovery completed: {recovery_stats}")
    
    # Verify no events remain pending
    remaining = outbox.get_pending_events(task_id)
    print(f"Remaining pending events: {len(remaining)}")


if __name__ == "__main__":
    print("=== Basic Usage Example ===")
    example_usage()
    
    print("\n=== Recovery Example ===")
    recovery_example()