#!/usr/bin/env python3
"""
Event Recovery Service Demonstration

This script demonstrates the event recovery functionality after Python Agent restart.
It simulates a scenario where events are persisted before delivery, the agent crashes,
and then recovers the events on restart.

Run this script to see the recovery service in action:
    python examples/recovery_service_demo.py
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

import sys
from pathlib import Path

# Add python-agent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.control_plane_client import ControlPlaneClient, PublishEventResult
from outbox.redis_outbox import RedisOutbox
from outbox.recovery_service import EventRecoveryService, RecoveryConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MockControlPlaneClient:
    """Mock Control Plane client for demonstration."""
    
    def __init__(self, simulate_failures: bool = False):
        self.simulate_failures = simulate_failures
        self.delivery_count = 0
        self.delivered_events = []
    
    def publish_event_with_retry_result(
        self, 
        task_id: str, 
        event: dict, 
        **kwargs
    ) -> PublishEventResult:
        """Mock event delivery with optional failure simulation."""
        self.delivery_count += 1
        
        # Simulate some failures for demonstration
        if self.simulate_failures and self.delivery_count % 3 == 0:
            logger.warning(f"Simulating delivery failure for event {event['eventId']}")
            return PublishEventResult(
                response=None,
                attempts=2,
                total_delay_seconds=1.0,
                circuit_breaker_triggered=False,
                final_error=Exception("Simulated delivery failure")
            )
        
        # Successful delivery
        self.delivered_events.append((task_id, event))
        logger.info(f"Successfully delivered event {event['eventId']} for task {task_id}")
        
        return PublishEventResult(
            response={"ok": True, "eventId": event["eventId"]},
            attempts=1,
            total_delay_seconds=0.1,
            circuit_breaker_triggered=False,
            final_error=None
        )


def create_sample_events(task_id: str, count: int) -> list[dict]:
    """Create sample events for demonstration."""
    events = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(count):
        event = {
            "eventId": f"evt_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": task_id,
            "assistant": "demo-agent",
            "type": f"DEMO_EVENT_{i}",
            "timestamp": base_time.isoformat().replace("+00:00", "Z"),
            "seq": i,
            "payload": {
                "message": f"Demo event {i}",
                "step": f"step_{i}",
                "data": {"value": i * 10}
            }
        }
        events.append(event)
    
    return events


def simulate_agent_crash_scenario():
    """
    Simulate a scenario where the agent crashes with pending events,
    then recovers them on restart.
    """
    logger.info("=== Event Recovery Service Demonstration ===")
    
    # Phase 1: Simulate normal operation with event persistence
    logger.info("\n--- Phase 1: Normal Operation ---")
    
    # Create outbox (using memory backend for demo)
    outbox = RedisOutbox(backend="memory", namespace="demo:outbox")
    
    # Create sample events for multiple tasks
    task_ids = ["task_web_gen_123", "task_backend_456", "task_fullstack_789"]
    all_events = []
    
    for task_id in task_ids:
        events = create_sample_events(task_id, 3)
        all_events.extend(events)
        
        # Store events in outbox (simulating persistence before delivery)
        for event in events:
            outbox.store_event(task_id, event)
            logger.info(f"Stored event {event['eventId']} in outbox for task {task_id}")
    
    # Show pending events before "crash"
    logger.info(f"\nTotal events stored in outbox: {len(all_events)}")
    for task_id in task_ids:
        pending = outbox.get_pending_events(task_id)
        logger.info(f"Task {task_id}: {len(pending)} pending events")
    
    # Phase 2: Simulate agent crash (events remain in outbox)
    logger.info("\n--- Phase 2: Agent Crash (Events Persist) ---")
    logger.info("Simulating agent crash... Events remain in persistent outbox")
    time.sleep(1)
    
    # Phase 3: Agent restart and recovery
    logger.info("\n--- Phase 3: Agent Restart and Recovery ---")
    
    # Create mock client (simulating Control Plane availability)
    mock_client = MockControlPlaneClient(simulate_failures=True)
    
    # Create recovery service
    recovery_config = RecoveryConfig(
        enabled=True,
        startup_delay_seconds=0.5,
        max_retry_attempts=3,
        retry_backoff_seconds=0.5,
        batch_size=5,
        sequence_gap_detection=True,
    )
    
    recovery_service = EventRecoveryService(
        outbox=outbox,
        client=mock_client,
        config=recovery_config
    )
    
    # Set up callbacks for demonstration
    recovered_events = []
    
    def on_recovery_start():
        logger.info("🔄 Recovery process started")
    
    def on_recovery_complete(stats):
        logger.info(f"✅ Recovery completed: {stats.successful_deliveries} delivered, "
                   f"{stats.failed_deliveries} failed")
    
    def on_event_recovered(task_id, event):
        recovered_events.append((task_id, event))
        logger.info(f"📤 Recovered event {event['eventId']} for task {task_id}")
    
    recovery_service.set_recovery_callbacks(
        on_start=on_recovery_start,
        on_complete=on_recovery_complete,
        on_event_recovered=on_event_recovered
    )
    
    # Perform recovery
    logger.info("Starting event recovery...")
    stats = recovery_service.recover_events_now()
    
    # Phase 4: Show recovery results
    logger.info("\n--- Phase 4: Recovery Results ---")
    
    logger.info(f"Recovery Statistics:")
    logger.info(f"  Tasks scanned: {stats.total_tasks_scanned}")
    logger.info(f"  Events found: {stats.total_events_found}")
    logger.info(f"  Successful deliveries: {stats.successful_deliveries}")
    logger.info(f"  Failed deliveries: {stats.failed_deliveries}")
    logger.info(f"  Tasks with failures: {stats.tasks_with_failures}")
    logger.info(f"  Recovery duration: {stats.recovery_duration_seconds}s")
    logger.info(f"  Sequence gaps detected: {stats.sequence_gaps_detected}")
    logger.info(f"  Sequence gaps resolved: {stats.sequence_gaps_resolved}")
    
    # Show remaining events in outbox
    logger.info(f"\nRemaining events in outbox:")
    total_remaining = 0
    for task_id in task_ids:
        remaining = outbox.get_pending_events(task_id)
        total_remaining += len(remaining)
        if remaining:
            logger.info(f"  Task {task_id}: {len(remaining)} events still pending")
            for event in remaining:
                logger.info(f"    - {event['eventId']} ({event['type']})")
        else:
            logger.info(f"  Task {task_id}: All events recovered ✅")
    
    if total_remaining == 0:
        logger.info("  🎉 All events successfully recovered!")
    
    # Show delivered events
    logger.info(f"\nDelivered events ({len(mock_client.delivered_events)}):")
    for task_id, event in mock_client.delivered_events:
        logger.info(f"  ✅ {event['eventId']} ({event['type']}) -> Task {task_id}")
    
    # Phase 5: Demonstrate idempotency
    logger.info("\n--- Phase 5: Recovery Idempotency ---")
    logger.info("Running recovery again to demonstrate idempotency...")
    
    # Reset client counters
    initial_delivery_count = mock_client.delivery_count
    
    # Run recovery again
    stats2 = recovery_service.recover_events_now()
    
    logger.info(f"Second recovery results:")
    logger.info(f"  Events found: {stats2.total_events_found}")
    logger.info(f"  New deliveries: {mock_client.delivery_count - initial_delivery_count}")
    
    if stats2.total_events_found == 0:
        logger.info("  ✅ Recovery is idempotent - no duplicate deliveries!")
    
    logger.info("\n=== Demonstration Complete ===")


def demonstrate_sequence_continuity():
    """Demonstrate sequence continuity across restarts."""
    logger.info("\n=== Sequence Continuity Demonstration ===")
    
    # Create outbox with events that have sequence gaps
    outbox = RedisOutbox(backend="memory", namespace="sequence:demo")
    task_id = "task_sequence_demo"
    
    # Create events with intentional gaps: sequences 0, 1, 4, 7
    gap_sequences = [0, 1, 4, 7]
    events = []
    
    for seq in gap_sequences:
        event = {
            "eventId": f"evt_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": task_id,
            "assistant": "sequence-demo-agent",
            "type": f"SEQUENCE_EVENT_{seq}",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": seq,
            "payload": {"sequence": seq, "message": f"Event with sequence {seq}"}
        }
        events.append(event)
        outbox.store_event(task_id, event)
        logger.info(f"Stored event with sequence {seq}")
    
    # Create recovery service with gap detection enabled
    mock_client = MockControlPlaneClient(simulate_failures=False)
    recovery_config = RecoveryConfig(
        enabled=True,
        startup_delay_seconds=0.0,
        sequence_gap_detection=True,
    )
    
    recovery_service = EventRecoveryService(
        outbox=outbox,
        client=mock_client,
        config=recovery_config
    )
    
    # Perform recovery
    logger.info("\nPerforming recovery with sequence gap detection...")
    stats = recovery_service.recover_events_now()
    
    logger.info(f"Sequence continuity results:")
    logger.info(f"  Sequence gaps detected: {stats.sequence_gaps_detected}")
    logger.info(f"  Sequence gaps resolved: {stats.sequence_gaps_resolved}")
    logger.info(f"  All events delivered: {stats.successful_deliveries == len(events)}")
    
    # Show the sequence gaps that were detected
    expected_gaps = 2 + 2  # Gap from 1->4 (2 missing) + gap from 4->7 (2 missing)
    if stats.sequence_gaps_detected == expected_gaps:
        logger.info(f"  ✅ Correctly detected {expected_gaps} missing sequence numbers")
    else:
        logger.info(f"  ⚠️  Expected {expected_gaps} gaps, detected {stats.sequence_gaps_detected}")
    
    logger.info("=== Sequence Continuity Demo Complete ===")


if __name__ == "__main__":
    try:
        # Run main crash/recovery demonstration
        simulate_agent_crash_scenario()
        
        # Run sequence continuity demonstration
        demonstrate_sequence_continuity()
        
    except KeyboardInterrupt:
        logger.info("\nDemo interrupted by user")
    except Exception as exc:
        logger.error(f"Demo failed with error: {exc}", exc_info=True)