"""
Unit tests for Redis-based persistent outbox implementation.

Tests cover event persistence, validation, atomic operations, and recovery scenarios.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from outbox.redis_outbox import RedisOutbox, EventValidationError, RedisOutboxError


def test_redis_outbox_initialization():
    """Test Redis outbox initialization with different backends."""
    # Test memory backend
    outbox = RedisOutbox(backend="memory")
    assert outbox.backend == "memory"
    assert not outbox._redis_enabled
    
    # Test redis backend (will fall back to memory if Redis unavailable)
    outbox = RedisOutbox(backend="redis")
    assert outbox.backend == "redis"
    
    # Test default namespace
    assert outbox.namespace == "autocode:outbox"
    
    # Test custom namespace
    outbox = RedisOutbox(backend="memory", namespace="test:outbox")
    assert outbox.namespace == "test:outbox"


def test_event_validation():
    """Test event validation against JSON schema."""
    outbox = RedisOutbox(backend="memory")
    
    # Valid event
    valid_event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    # Should not raise exception
    outbox.store_event("task_123", valid_event)
    
    # Invalid event - missing required field
    invalid_event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        # Missing taskId
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    with pytest.raises(EventValidationError):
        outbox.store_event("task_123", invalid_event)
    
    # Invalid event - wrong eventId format
    invalid_event_id = {
        "eventId": "invalid_id",  # Should start with "evt_"
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    with pytest.raises(EventValidationError):
        outbox.store_event("task_123", invalid_event_id)


def test_event_storage_and_retrieval():
    """Test basic event storage and retrieval operations."""
    outbox = RedisOutbox(backend="memory")
    
    event1 = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    event2 = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_PROGRESS",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 1,
        "payload": {"message": "Task in progress"}
    }
    
    # Store events
    outbox.store_event("task_123", event1)
    outbox.store_event("task_123", event2)
    
    # Retrieve pending events
    pending = outbox.get_pending_events("task_123")
    assert len(pending) == 2
    assert pending[0]["eventId"] == event1["eventId"]
    assert pending[1]["eventId"] == event2["eventId"]
    
    # Events should be sorted by sequence number
    assert pending[0]["seq"] <= pending[1]["seq"]


def test_event_acknowledgment():
    """Test event acknowledgment and removal from outbox."""
    outbox = RedisOutbox(backend="memory")
    
    event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    # Store event
    outbox.store_event("task_123", event)
    assert len(outbox.get_pending_events("task_123")) == 1
    
    # Acknowledge event
    result = outbox.acknowledge_event("task_123", event["eventId"])
    assert result is True
    assert len(outbox.get_pending_events("task_123")) == 0
    
    # Acknowledge non-existent event
    result = outbox.acknowledge_event("task_123", "evt_nonexistent")
    assert result is False


def test_sequence_number_management():
    """Test sequence number generation and management."""
    outbox = RedisOutbox(backend="memory")
    
    # Initial sequence should be 0
    seq1 = outbox.get_next_sequence("task_123")
    assert seq1 == 0
    
    # Store an event to increment sequence
    event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    outbox.store_event("task_123", event)
    
    # Next sequence should be incremented
    seq2 = outbox.get_next_sequence("task_123")
    assert seq2 == 1


def test_multiple_tasks():
    """Test outbox operations with multiple tasks."""
    outbox = RedisOutbox(backend="memory")
    
    # Create events for different tasks
    event1 = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task 123 started"}
    }
    
    event2 = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_456",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task 456 started"}
    }
    
    # Store events for different tasks
    outbox.store_event("task_123", event1)
    outbox.store_event("task_456", event2)
    
    # Check pending events per task
    pending_123 = outbox.get_pending_events("task_123")
    pending_456 = outbox.get_pending_events("task_456")
    
    assert len(pending_123) == 1
    assert len(pending_456) == 1
    assert pending_123[0]["taskId"] == "task_123"
    assert pending_456[0]["taskId"] == "task_456"
    
    # Check all pending tasks
    all_tasks = outbox.get_all_pending_tasks()
    assert "task_123" in all_tasks
    assert "task_456" in all_tasks


def test_task_cleanup():
    """Test task cleanup functionality."""
    outbox = RedisOutbox(backend="memory")
    
    event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    # Store event
    outbox.store_event("task_123", event)
    assert len(outbox.get_pending_events("task_123")) == 1
    assert "task_123" in outbox.get_all_pending_tasks()
    
    # Cleanup task
    outbox.cleanup_task("task_123")
    assert len(outbox.get_pending_events("task_123")) == 0
    assert "task_123" not in outbox.get_all_pending_tasks()


def test_empty_task_id_handling():
    """Test handling of empty or invalid task IDs."""
    outbox = RedisOutbox(backend="memory")
    
    event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    # Empty task ID should raise error
    with pytest.raises(RedisOutboxError):
        outbox.store_event("", event)
    
    with pytest.raises(RedisOutboxError):
        outbox.store_event("   ", event)
    
    # Other operations should handle empty task IDs gracefully
    assert outbox.get_pending_events("") == []
    assert outbox.get_next_sequence("") == 0
    assert outbox.acknowledge_event("", "evt_123") is False


def test_event_ordering():
    """Test that events are returned in sequence order."""
    outbox = RedisOutbox(backend="memory")
    
    # Create events with different sequence numbers (out of order)
    events = []
    for i, seq in enumerate([2, 0, 1, 3]):
        event = {
            "eventId": f"evt_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": "task_123",
            "assistant": "ai-agent",
            "type": f"EVENT_{i}",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": seq,
            "payload": {"message": f"Event {i}"}
        }
        events.append(event)
        outbox.store_event("task_123", event)
    
    # Retrieve events - should be ordered by sequence
    pending = outbox.get_pending_events("task_123")
    assert len(pending) == 4
    
    # Check sequence order
    for i in range(len(pending) - 1):
        assert pending[i]["seq"] <= pending[i + 1]["seq"]


def test_optional_session_id():
    """Test handling of optional sessionId field."""
    outbox = RedisOutbox(backend="memory")
    
    # Event with sessionId
    event_with_session = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"},
        "sessionId": "session_456"
    }
    
    # Should store successfully
    outbox.store_event("task_123", event_with_session)
    
    # Event without sessionId
    event_without_session = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_PROGRESS",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 1,
        "payload": {"message": "Task in progress"}
    }
    
    # Should also store successfully
    outbox.store_event("task_123", event_without_session)
    
    # Both events should be retrievable
    pending = outbox.get_pending_events("task_123")
    assert len(pending) == 2


def test_concurrent_operations():
    """Test thread safety of outbox operations."""
    import threading
    import time
    
    outbox = RedisOutbox(backend="memory")
    results = []
    errors = []
    
    def store_events(task_id: str, count: int):
        """Store multiple events for a task."""
        try:
            for i in range(count):
                event = {
                    "eventId": f"evt_{uuid4().hex}",
                    "eventVersion": 1,
                    "taskId": task_id,
                    "assistant": "ai-agent",
                    "type": f"EVENT_{i}",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "seq": i,
                    "payload": {"message": f"Event {i}"}
                }
                outbox.store_event(task_id, event)
                time.sleep(0.001)  # Small delay to simulate real conditions
            results.append(f"Stored {count} events for {task_id}")
        except Exception as e:
            errors.append(str(e))
    
    # Start multiple threads storing events
    threads = []
    for i in range(3):
        thread = threading.Thread(target=store_events, args=(f"task_{i}", 5))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 3
    
    # Verify all events were stored
    for i in range(3):
        pending = outbox.get_pending_events(f"task_{i}")
        assert len(pending) == 5


def test_redis_fallback_behavior():
    """Test fallback to local storage when Redis is unavailable."""
    # Create outbox with Redis backend but no actual Redis connection
    outbox = RedisOutbox(backend="redis", redis_url="redis://nonexistent:6379/0")
    
    # Should fall back to local storage
    assert not outbox._redis_enabled
    
    # Operations should still work with local storage
    event = {
        "eventId": "evt_" + uuid4().hex,
        "eventVersion": 1,
        "taskId": "task_123",
        "assistant": "ai-agent",
        "type": "TASK_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seq": 0,
        "payload": {"message": "Task started"}
    }
    
    outbox.store_event("task_123", event)
    pending = outbox.get_pending_events("task_123")
    assert len(pending) == 1
    assert pending[0]["eventId"] == event["eventId"]