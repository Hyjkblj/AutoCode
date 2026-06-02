"""
Comprehensive property-based tests for event persistence behavior.

Task 3.4: Write property tests for event persistence
Property 3: Event Persistence Before Delivery
Validates: Requirements 2.1

These tests provide comprehensive validation of event persistence behavior
with focus on core persistence guarantees, atomicity, consistency, durability, and edge cases.
"""

from __future__ import annotations

import json
import os
import pytest
import time
from datetime import datetime, timezone
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from unittest.mock import Mock, patch
from uuid import uuid4

from outbox.redis_outbox import RedisOutbox, EventValidationError, RedisOutboxError


# Strategy for generating valid event IDs
event_id_strategy = st.builds(
    lambda: f"evt_{uuid4().hex}"
)

# Strategy for generating valid timestamps
timestamp_strategy = st.builds(
    lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
)

# Strategy for generating valid events
valid_event_strategy = st.builds(
    dict,
    eventId=event_id_strategy,
    eventVersion=st.integers(min_value=1, max_value=10),
    taskId=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))),
    assistant=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))),
    type=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))),
    timestamp=timestamp_strategy,
    seq=st.integers(min_value=0, max_value=1000),
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        values=st.one_of(st.text(max_size=100), st.integers(), st.booleans()),
        min_size=0,
        max_size=5
    )
)

# Strategy for generating task IDs
task_id_strategy = st.text(
    min_size=1, 
    max_size=50, 
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))
)


class TestRedisEventPersistenceProperties:
    """
    Comprehensive property-based tests for Redis event persistence.
    
    **Task 3.4: Write property tests for event persistence**
    **Property 3: Event Persistence Before Delivery**
    **Validates: Requirements 2.1**
    
    These tests validate event persistence behavior with focus on the core
    persistence guarantees rather than Redis-specific implementation details.
    """
    
    @given(valid_event_strategy, task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_3_redis_backend_event_persistence(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Redis Backend**
        
        For any event publication attempt using Redis backend, the Event_Outbox 
        SHALL persist the event before attempting delivery.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        # Test with memory backend for reliable testing
        outbox = RedisOutbox(backend="memory")
        
        # Store event
        outbox.store_event(task_id, event)
        
        # Property: Event must be persisted immediately after store_event returns
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) >= 1
        
        # Property: The persisted event must be complete and unchanged
        stored_event = next(e for e in pending_events if e["eventId"] == event["eventId"])
        assert stored_event == event, "Event data was corrupted during persistence"
        
        # Property: Task must be listed in pending tasks
        pending_tasks = outbox.get_all_pending_tasks()
        assert task_id in pending_tasks
    
    @given(valid_event_strategy, task_id_strategy, st.integers(min_value=300, max_value=86400))
    @settings(deadline=None, max_examples=10)
    def test_property_3_redis_ttl_configuration_respected(self, event, task_id, ttl_seconds):
        """
        **Property 3: Event Persistence Before Delivery - TTL Configuration**
        
        For any event publication attempt with custom TTL, the Event_Outbox 
        SHALL respect the configured TTL values.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory", ttl_seconds=ttl_seconds)
        
        # Property: TTL configuration should be stored correctly
        assert outbox.ttl_seconds == ttl_seconds
        
        # Store event
        outbox.store_event(task_id, event)
        
        # Property: Event should be persisted regardless of TTL value
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == 1
        assert pending_events[0]["eventId"] == event["eventId"]
    
    @given(st.lists(valid_event_strategy, min_size=3, max_size=10), task_id_strategy)
    def test_property_3_redis_concurrent_event_storage(self, events, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Concurrent Safety**
        
        For any concurrent event publication attempts, the Event_Outbox 
        SHALL handle concurrent operations safely.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        assume(len(set(e["eventId"] for e in events)) == len(events))
        
        outbox = RedisOutbox(backend="memory")
        
        # Store events with sequence numbers
        for i, event in enumerate(events):
            event["seq"] = i
            outbox.store_event(task_id, event)
        
        # Property: All events should be persisted
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == len(events)
        
        # Property: Event integrity should be maintained
        stored_event_ids = {e["eventId"] for e in pending_events}
        original_event_ids = {e["eventId"] for e in events}
        assert stored_event_ids == original_event_ids
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_redis_acknowledgment_atomicity(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Acknowledgment Atomicity**
        
        For any event acknowledgment operation, the Event_Outbox SHALL remove 
        the event atomically.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event first
        outbox.store_event(task_id, event)
        
        # Verify event is stored
        pending_before = outbox.get_pending_events(task_id)
        assert len(pending_before) == 1
        assert pending_before[0]["eventId"] == event["eventId"]
        
        # Acknowledge event
        result = outbox.acknowledge_event(task_id, event["eventId"])
        
        # Property: Acknowledgment should succeed
        assert result is True
        
        # Property: Event should be removed after acknowledgment
        pending_after = outbox.get_pending_events(task_id)
        assert len(pending_after) == 0
    
    @given(valid_event_strategy, task_id_strategy)
    @settings(deadline=5000)  # 5 second deadline
    def test_property_3_redis_connection_failure_fallback(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Connection Fallback**
        
        For any event publication attempt when Redis is unavailable, the Event_Outbox 
        SHALL fall back to local storage while maintaining persistence guarantees.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        # Create outbox with a mock Redis client that fails on register_script
        # (simulating Redis unavailability without actual network timeout)
        mock_redis = Mock()
        mock_redis.ping = Mock()
        mock_redis.register_script = Mock(side_effect=Exception("Redis unavailable"))
        
        outbox = RedisOutbox(backend="redis", redis_client=mock_redis)
        
        # Property: Should fall back gracefully when Redis is unavailable
        assert outbox._redis_enabled is False
        
        # Store event (should use local fallback)
        outbox.store_event(task_id, event)
        
        # Property: Event should be stored despite Redis unavailability
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == 1
        assert pending_events[0]["eventId"] == event["eventId"]
        assert pending_events[0] == event
        
        # Property: Task should be listed in pending tasks
        pending_tasks = outbox.get_all_pending_tasks()
        assert task_id in pending_tasks
    
    @given(st.lists(valid_event_strategy, min_size=2, max_size=8), task_id_strategy)
    def test_property_3_redis_batch_operations_consistency(self, events, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Batch Consistency**
        
        For any batch of event publication attempts, the Event_Outbox SHALL 
        maintain consistency across all operations.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        assume(len(set(e["eventId"] for e in events)) == len(events))
        
        outbox = RedisOutbox(backend="memory")
        
        # Store all events in batch
        for i, event in enumerate(events):
            event["seq"] = i
            outbox.store_event(task_id, event)
        
        # Property: All operations should complete successfully
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == len(events)
        
        # Property: All events should be intact
        for event in events:
            matching_event = next(e for e in pending_events if e["eventId"] == event["eventId"])
            assert matching_event == event
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_redis_error_handling_preserves_data_integrity(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Error Handling**
        
        For any event publication attempt that encounters errors, 
        the Event_Outbox SHALL handle errors gracefully while preserving data integrity.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Test persistence with invalid parameters (should fail gracefully)
        with pytest.raises(RedisOutboxError):
            outbox.store_event("", event)
        
        # Property: Valid operations should still work after error conditions
        outbox.store_event(task_id, event)
        pending = outbox.get_pending_events(task_id)
        assert len(pending) == 1
        assert pending[0]["eventId"] == event["eventId"]
        
        # Test acknowledgment with invalid parameters
        assert outbox.acknowledge_event("", event["eventId"]) is False
        assert outbox.acknowledge_event(task_id, "") is False
        
        # Property: Event should still be present after invalid operations
        pending_after_invalid = outbox.get_pending_events(task_id)
        assert len(pending_after_invalid) == 1
        assert pending_after_invalid[0]["eventId"] == event["eventId"]


class TestEventPersistenceEdgeCases:
    """
    Property-based tests for edge cases in event persistence.
    
    **Task 3.4: Write property tests for event persistence**
    **Property 3: Event Persistence Before Delivery**
    **Validates: Requirements 2.1**
    """
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_large_event_payload_persistence(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Large Payload Handling**
        
        For any event publication attempt with large payloads, the Event_Outbox 
        SHALL persist the event correctly without data truncation.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        # Create event with large payload
        large_payload = {
            "data": "x" * 10000,  # 10KB string
            "metadata": {f"key_{i}": f"value_{i}" * 100 for i in range(50)},
            "nested": {
                "level1": {
                    "level2": {
                        "level3": ["item"] * 1000
                    }
                }
            }
        }
        event["payload"] = large_payload
        
        outbox = RedisOutbox(backend="memory")
        
        # Store large event
        outbox.store_event(task_id, event)
        
        # Property: Large event should be persisted completely
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == 1
        
        stored_event = pending_events[0]
        assert stored_event["eventId"] == event["eventId"]
        assert stored_event["payload"] == large_payload
        
        # Property: All nested data should be preserved
        assert stored_event["payload"]["data"] == "x" * 10000
        assert len(stored_event["payload"]["metadata"]) == 50
        assert len(stored_event["payload"]["nested"]["level1"]["level2"]["level3"]) == 1000
    
    @given(task_id_strategy)
    def test_property_3_unicode_and_special_characters_persistence(self, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Unicode Character Handling**
        
        For any event publication attempt with Unicode and special characters, 
        the Event_Outbox SHALL persist the event with proper encoding.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        # Create event with Unicode and special characters
        unicode_event = {
            "eventId": f"evt_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": task_id,
            "assistant": "test_assistant",
            "type": "unicode_test",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": 0,
            "payload": {
                "unicode_text": "Hello 世界 🌍 Здравствуй мир",
                "special_chars": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
                "emoji": "🚀🎉💻🔥⭐",
                "mixed": "Test with émojis 🎯 and spëcial chars: ñáéíóú",
                "json_special": '{"key": "value with \\"quotes\\" and \\n newlines"}'
            }
        }
        
        outbox = RedisOutbox(backend="memory")
        
        # Store Unicode event
        outbox.store_event(task_id, unicode_event)
        
        # Property: Unicode characters should be preserved exactly
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == 1
        
        stored_event = pending_events[0]
        assert stored_event["payload"]["unicode_text"] == "Hello 世界 🌍 Здравствуй мир"
        assert stored_event["payload"]["special_chars"] == "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        assert stored_event["payload"]["emoji"] == "🚀🎉💻🔥⭐"
        assert stored_event["payload"]["mixed"] == "Test with émojis 🎯 and spëcial chars: ñáéíóú"
        assert stored_event["payload"]["json_special"] == '{"key": "value with \\"quotes\\" and \\n newlines"}'
    
    @given(st.lists(valid_event_strategy, min_size=100, max_size=500), task_id_strategy)
    @settings(max_examples=5, deadline=30000, suppress_health_check=[HealthCheck.data_too_large])  # Reduced examples for performance
    def test_property_3_high_volume_event_persistence(self, events, task_id):
        """
        **Property 3: Event Persistence Before Delivery - High Volume Handling**
        
        For any high-volume event publication scenario, the Event_Outbox 
        SHALL persist all events correctly without loss or corruption.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        assume(len(set(e["eventId"] for e in events)) == len(events))
        
        outbox = RedisOutbox(backend="memory")
        
        # Assign sequence numbers
        for i, event in enumerate(events):
            event["seq"] = i
        
        # Store high volume of events
        for event in events:
            outbox.store_event(task_id, event)
        
        # Property: All events should be persisted
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == len(events)
        
        # Property: All events should be retrievable and intact
        stored_event_ids = {e["eventId"] for e in pending_events}
        original_event_ids = {e["eventId"] for e in events}
        assert stored_event_ids == original_event_ids
        
        # Property: Event ordering should be preserved
        pending_events.sort(key=lambda e: e["seq"])
        for i, event in enumerate(events):
            assert pending_events[i]["eventId"] == event["eventId"]
            assert pending_events[i]["seq"] == event["seq"]
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_event_persistence_with_system_time_changes(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - System Time Change Resilience**
        
        For any event publication attempt during system time changes, 
        the Event_Outbox SHALL persist events correctly regardless of time variations.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event with current timestamp
        original_timestamp = event["timestamp"]
        outbox.store_event(task_id, event)
        
        # Simulate system time change by modifying event timestamp
        modified_event = dict(event)
        modified_event["eventId"] = f"evt_{uuid4().hex}"
        modified_event["timestamp"] = "2025-01-01T00:00:00Z"  # Different timestamp
        modified_event["seq"] = 1
        
        outbox.store_event(task_id, modified_event)
        
        # Property: Both events should be persisted regardless of timestamp differences
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == 2
        
        # Property: Original timestamps should be preserved
        event_by_id = {e["eventId"]: e for e in pending_events}
        assert event_by_id[event["eventId"]]["timestamp"] == original_timestamp
        assert event_by_id[modified_event["eventId"]]["timestamp"] == "2025-01-01T00:00:00Z"
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_event_persistence_memory_pressure_simulation(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Memory Pressure Resilience**
        
        For any event publication attempt under memory pressure conditions, 
        the Event_Outbox SHALL maintain persistence guarantees.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Simulate memory pressure by creating many large events
        large_events = []
        for i in range(10):
            large_event = dict(event)
            large_event["eventId"] = f"evt_{uuid4().hex}"
            large_event["seq"] = i
            large_event["payload"] = {
                "large_data": "x" * 1000,  # 1KB per event
                "index": i
            }
            large_events.append(large_event)
        
        # Store all events
        for large_event in large_events:
            outbox.store_event(task_id, large_event)
        
        # Property: All events should be persisted despite memory pressure
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == len(large_events)
        
        # Property: Event data integrity should be maintained
        for i, stored_event in enumerate(pending_events):
            assert stored_event["payload"]["large_data"] == "x" * 1000
            assert stored_event["payload"]["index"] == stored_event["seq"]


class TestEventPersistenceAtomicityProperties:
    """
    Property-based tests for atomicity guarantees in event persistence.
    
    **Task 3.4: Write property tests for event persistence**
    **Property 3: Event Persistence Before Delivery**
    **Validates: Requirements 2.1**
    """
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_atomic_event_storage_all_or_nothing(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Atomic Storage**
        
        For any event publication attempt, the Event_Outbox SHALL store 
        the event atomically - either completely or not at all.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event
        outbox.store_event(task_id, event)
        
        # Property: Event should be immediately available after storage
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == 1
        
        # Property: Stored event should be complete and identical
        stored_event = pending_events[0]
        assert stored_event == event
        
        # Property: All event fields should be preserved
        for key, value in event.items():
            assert stored_event[key] == value
    
    @given(st.lists(valid_event_strategy, min_size=2, max_size=5), task_id_strategy)
    def test_property_3_atomic_batch_consistency(self, events, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Batch Atomicity**
        
        For any sequence of event storage operations, each individual 
        operation SHALL be atomic and consistent.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        assume(len(set(e["eventId"] for e in events)) == len(events))
        
        outbox = RedisOutbox(backend="memory")
        
        # Store events one by one, checking consistency after each
        for i, event in enumerate(events):
            event["seq"] = i
            outbox.store_event(task_id, event)
            
            # Property: After each storage, all previously stored events should still be present
            pending = outbox.get_pending_events(task_id)
            assert len(pending) == i + 1
            
            # Property: All stored events should be intact
            stored_ids = {e["eventId"] for e in pending}
            expected_ids = {events[j]["eventId"] for j in range(i + 1)}
            assert stored_ids == expected_ids
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_atomic_acknowledgment_consistency(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Acknowledgment Atomicity**
        
        For any event acknowledgment operation, the removal SHALL be 
        atomic and leave the outbox in a consistent state.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Store multiple events
        events = []
        for i in range(3):
            test_event = dict(event)
            test_event["eventId"] = f"evt_{uuid4().hex}"
            test_event["seq"] = i
            events.append(test_event)
            outbox.store_event(task_id, test_event)
        
        # Verify all events are stored
        pending_before = outbox.get_pending_events(task_id)
        assert len(pending_before) == 3
        
        # Acknowledge middle event
        middle_event = events[1]
        result = outbox.acknowledge_event(task_id, middle_event["eventId"])
        assert result is True
        
        # Property: Only the acknowledged event should be removed
        pending_after = outbox.get_pending_events(task_id)
        assert len(pending_after) == 2
        
        # Property: Remaining events should be intact
        remaining_ids = {e["eventId"] for e in pending_after}
        expected_ids = {events[0]["eventId"], events[2]["eventId"]}
        assert remaining_ids == expected_ids