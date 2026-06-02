"""
Example demonstrating ACK response handling in ControlPlaneClient.

This example shows how to use the enhanced event publishing methods that handle
ACK responses from the Control Plane, implementing Requirements 2.4 and 2.5.
"""

import logging
import time
from client.control_plane_client import ControlPlaneClient, ControlPlaneRequestError
from utils.observability import TaskObservability

# Configure logging to see ACK response details
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def demonstrate_ack_response_handling():
    """Demonstrate various ACK response scenarios."""
    
    # Initialize client
    client = ControlPlaneClient(
        base_url="http://localhost:8058",
        agent_token="your-agent-token",
        timeout_seconds=15
    )
    
    # Initialize observability context
    observability = TaskObservability(
        trace_id="trace-123",
        run_id="run-456"
    )
    
    task_id = "task-example-123"
    
    print("=== ACK Response Handling Examples ===\n")
    
    # Example 1: Successful event with ACK response
    print("1. Publishing event with successful ACK response:")
    try:
        event = {
            "type": "TASK_STARTED",
            "eventId": f"evt-{int(time.time())}",
            "seq": 1,
            "timestamp": "2024-01-15T10:00:00Z",
            "payload": {"status": "started"}
        }
        
        # Method 1: Get only ACK response data
        ack_response = client.publish_event_with_ack(
            task_id, 
            event, 
            observability=observability
        )
        
        if ack_response:
            print(f"   ✓ Event acknowledged:")
            print(f"     - Sequence: {ack_response['seq']}")
            print(f"     - Accepted: {ack_response['accepted']}")
            print(f"     - Duplicate: {ack_response['duplicate']}")
            print(f"     - Error Code: {ack_response['errorCode']}")
        else:
            print("   ✗ No ACK response received")
            
    except ControlPlaneRequestError as e:
        print(f"   ✗ Event delivery failed: {e}")
        print(f"     - Retryable: {e.retryable}")
    
    print()
    
    # Example 2: Get full retry result with ACK response
    print("2. Publishing event with full retry result:")
    try:
        event = {
            "type": "TASK_PROGRESS",
            "eventId": f"evt-{int(time.time())}",
            "seq": 2,
            "timestamp": "2024-01-15T10:01:00Z",
            "payload": {"progress": 50}
        }
        
        # Method 2: Get full result including retry metrics
        result = client.publish_event_with_retry_result(
            task_id,
            event,
            max_attempts=3,
            initial_backoff_seconds=1.0,
            observability=observability
        )
        
        print(f"   Delivery Result:")
        print(f"     - Attempts: {result.attempts}")
        print(f"     - Total Delay: {result.total_delay_seconds:.2f}s")
        print(f"     - Circuit Breaker Triggered: {result.circuit_breaker_triggered}")
        print(f"     - Final Error: {result.final_error}")
        
        if result.ack_response:
            print(f"   ACK Response:")
            print(f"     - Sequence: {result.ack_response['seq']}")
            print(f"     - Accepted: {result.ack_response['accepted']}")
            print(f"     - Duplicate: {result.ack_response['duplicate']}")
            print(f"     - Error Code: {result.ack_response['errorCode']}")
        
    except ControlPlaneRequestError as e:
        print(f"   ✗ Event delivery failed: {e}")
    
    print()
    
    # Example 3: Handle duplicate event
    print("3. Publishing duplicate event:")
    try:
        # Send the same event again (should be detected as duplicate)
        duplicate_event = {
            "type": "TASK_PROGRESS",
            "eventId": f"evt-{int(time.time())}",  # Same event ID
            "seq": 2,
            "timestamp": "2024-01-15T10:01:00Z",
            "payload": {"progress": 50}
        }
        
        ack_response = client.publish_event_with_ack(task_id, duplicate_event)
        
        if ack_response:
            if ack_response['duplicate']:
                print(f"   ✓ Duplicate event acknowledged (seq: {ack_response['seq']})")
            else:
                print(f"   ✓ Event processed normally (seq: {ack_response['seq']})")
        
    except ControlPlaneRequestError as e:
        print(f"   ✗ Event delivery failed: {e}")
    
    print()
    
    # Example 4: Handle validation errors
    print("4. Publishing invalid event (missing eventId):")
    try:
        invalid_event = {
            "type": "TASK_FAILED",
            # Missing eventId - should trigger MISSING_EVENT_ID error
            "seq": 3,
            "timestamp": "2024-01-15T10:02:00Z",
            "payload": {"error": "Something went wrong"}
        }
        
        ack_response = client.publish_event_with_ack(task_id, invalid_event, max_attempts=1)
        print(f"   Unexpected success: {ack_response}")
        
    except ControlPlaneRequestError as e:
        print(f"   ✓ Expected validation error: {e}")
        print(f"     - Retryable: {e.retryable}")
    
    print()
    
    # Example 5: Extract ACK response from raw response
    print("5. Manual ACK response extraction:")
    try:
        event = {
            "type": "TASK_COMPLETED",
            "eventId": f"evt-{int(time.time())}",
            "seq": 4,
            "timestamp": "2024-01-15T10:03:00Z",
            "payload": {"result": "success"}
        }
        
        # Use basic publish_event method
        raw_response = client.publish_event(task_id, event)
        
        if raw_response:
            print(f"   Raw response: {raw_response}")
            
            # Extract ACK response manually
            ack_response = client.extract_ack_response(raw_response)
            if ack_response:
                print(f"   Extracted ACK: {ack_response}")
                
                # Validate ACK response
                is_valid = client.validate_ack_response(ack_response, expected_seq=4)
                print(f"   ACK validation: {'✓ Valid' if is_valid else '✗ Invalid'}")
            else:
                print("   ✗ Could not extract ACK response")
        
    except ControlPlaneRequestError as e:
        print(f"   ✗ Event delivery failed: {e}")
    
    print()
    
    # Example 6: Show delivery metrics
    print("6. Event delivery metrics:")
    metrics = client.get_event_delivery_metrics()
    print(f"   Total Attempts: {metrics['totalAttempts']}")
    print(f"   Successful Deliveries: {metrics['successfulDeliveries']}")
    print(f"   Failed Deliveries: {metrics['failedDeliveries']}")
    print(f"   Success Rate: {metrics['successRate']}%")
    print(f"   Circuit Breaker State: {metrics['circuitBreakerState']}")


def demonstrate_error_handling():
    """Demonstrate error handling with ACK responses."""
    
    print("\n=== Error Handling Examples ===\n")
    
    client = ControlPlaneClient(
        base_url="http://localhost:8058",
        agent_token="invalid-token"  # This will cause authentication errors
    )
    
    # Example of handling non-retryable errors
    print("1. Non-retryable error (invalid token):")
    try:
        event = {
            "type": "TASK_STARTED",
            "eventId": f"evt-{int(time.time())}",
            "seq": 1,
            "timestamp": "2024-01-15T10:00:00Z",
            "payload": {"status": "started"}
        }
        
        client.publish_event_with_ack("task-123", event, max_attempts=1)
        
    except ControlPlaneRequestError as e:
        print(f"   ✗ Authentication failed: {e}")
        print(f"   - Status Code: {e.status_code}")
        print(f"   - Retryable: {e.retryable}")
    
    print()
    
    # Example of handling retryable errors with backoff
    print("2. Retryable error with exponential backoff:")
    
    # Simulate network issues by using invalid URL
    unreliable_client = ControlPlaneClient(
        base_url="http://localhost:9999",  # Non-existent service
        agent_token="test-token"
    )
    
    try:
        event = {
            "type": "TASK_STARTED",
            "eventId": f"evt-{int(time.time())}",
            "seq": 1,
            "timestamp": "2024-01-15T10:00:00Z",
            "payload": {"status": "started"}
        }
        
        result = unreliable_client.publish_event_with_retry_result(
            "task-123", 
            event, 
            max_attempts=3,
            initial_backoff_seconds=0.1  # Fast for demo
        )
        
        print(f"   Result: {result}")
        
    except ControlPlaneRequestError as e:
        print(f"   ✗ Network error after retries: {e}")
        print(f"   - Retryable: {e.retryable}")


if __name__ == "__main__":
    print("ACK Response Handling Example")
    print("=" * 50)
    
    # Note: This example requires a running Control Plane at localhost:8058
    # with proper authentication tokens configured
    
    try:
        demonstrate_ack_response_handling()
        demonstrate_error_handling()
        
    except Exception as e:
        print(f"\nExample failed: {e}")
        print("Make sure the Control Plane is running at http://localhost:8058")
        print("and you have valid authentication tokens configured.")