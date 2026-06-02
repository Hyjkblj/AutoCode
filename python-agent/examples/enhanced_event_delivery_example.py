#!/usr/bin/env python3
"""
Example demonstrating enhanced event delivery with retry, backoff, and Redis outbox integration.

This example shows how Task 3.2 integrates with Task 3.1 (Redis outbox) to provide
reliable event delivery with exponential backoff retry logic.

Usage:
    python examples/enhanced_event_delivery_example.py
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.control_plane_client import ControlPlaneClient
from outbox.redis_outbox import RedisOutbox
from utils.observability import TaskObservability

# Configure logging to see structured logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Demonstrate enhanced event delivery with outbox integration."""
    
    # Initialize components
    client = ControlPlaneClient(
        base_url="http://localhost:8058",
        agent_token="demo-token",
        timeout_seconds=10
    )
    
    outbox = RedisOutbox(
        backend="memory",  # Use memory backend for demo
        namespace="demo:outbox"
    )
    
    # Create observability context
    task_id = "demo-task-123"
    observability = TaskObservability(
        task_id=task_id,
        trace_id="trace-demo-456",
        run_id="run-demo-789",
        engine="demo"
    )
    
    # Create sample event
    event = {
        "eventId": "evt_" + "d" * 32,
        "eventVersion": 1,
        "taskId": task_id,
        "assistant": "demo-assistant",
        "type": "TASK_PROGRESS",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seq": 1,
        "payload": {
            "progress": 50,
            "message": "Task is 50% complete"
        }
    }
    
    print("=== Enhanced Event Delivery Demo ===")
    print(f"Task ID: {task_id}")
    print(f"Event Type: {event['type']}")
    print(f"Event ID: {event['eventId']}")
    print()
    
    # Step 1: Store event in outbox (Task 3.1 integration)
    print("1. Storing event in Redis outbox...")
    try:
        outbox.store_event(task_id, event)
        print("   ✓ Event stored in outbox successfully")
    except Exception as e:
        print(f"   ✗ Failed to store event: {e}")
        return
    
    # Step 2: Attempt delivery with retry and backoff (Task 3.2)
    print("\n2. Attempting event delivery with retry logic...")
    print("   (This will fail since Control Plane is not running, demonstrating retry behavior)")
    
    try:
        result = client.publish_event_with_retry_result(
            task_id,
            event,
            max_attempts=3,  # Reduced for demo
            initial_backoff_seconds=1.0,
            observability=observability
        )
        
        if result.response:
            print("   ✓ Event delivered successfully!")
            print(f"   Response: {result.response}")
            
            # Acknowledge in outbox
            outbox.acknowledge_event(task_id, event["eventId"])
            print("   ✓ Event acknowledged in outbox")
            
        else:
            print("   ✗ Event delivery failed after all retries")
            print(f"   Attempts: {result.attempts}")
            print(f"   Total delay: {result.total_delay_seconds:.1f}s")
            print(f"   Circuit breaker triggered: {result.circuit_breaker_triggered}")
            if result.final_error:
                print(f"   Final error: {result.final_error}")
    
    except Exception as e:
        print(f"   ✗ Event delivery failed with exception: {e}")
    
    # Step 3: Show pending events in outbox
    print("\n3. Checking outbox for pending events...")
    pending_events = outbox.get_pending_events(task_id)
    if pending_events:
        print(f"   Found {len(pending_events)} pending events:")
        for event in pending_events:
            print(f"   - {event['eventId']}: {event['type']}")
    else:
        print("   No pending events found")
    
    # Step 4: Show delivery metrics
    print("\n4. Event delivery metrics:")
    metrics = client.get_event_delivery_metrics()
    for key, value in metrics.items():
        print(f"   {key}: {value}")
    
    print("\n=== Demo Complete ===")
    print("\nKey features demonstrated:")
    print("• Event persistence in Redis outbox before delivery")
    print("• Exponential backoff retry logic (1s, 2s, 4s, 8s, 16s)")
    print("• Circuit breaker integration for failure detection")
    print("• Structured logging with trace/run IDs")
    print("• Event delivery metrics tracking")
    print("• Integration with observability framework")


if __name__ == "__main__":
    main()