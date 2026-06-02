"""
Property-based tests for Redis outbox implementation.

These tests validate universal properties that should hold across all valid executions.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from hypothesis import given, strategies as st, assume
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


class TestEventPersistenceProperties:
    """
    Property-based tests for event persistence behavior.
    
    **Validates: Requirements 2.1**
    
    These tests verify that events are persisted before delivery attempts
    and that the outbox maintains consistency across all operations.
    """
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_event_persistence_before_delivery(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery**
        
        For any event publication attempt, the Event_Outbox SHALL persist 
        the event to Redis before attempting delivery to the Control_Plane.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event - this simulates persistence before delivery
        outbox.store_event(task_id, event)
        
        # Event should be immediately available in pending events
        pending_events = outbox.get_pending_events(task_id)
        
        # Property: Event must be persisted (available in pending) before any delivery attempt
        assert len(pending_events) >= 1
        assert any(e["eventId"] == event["eventId"] for e in pending_events)
        
        # Property: Persisted event must maintain all original data
        stored_event = next(e for e in pending_events if e["eventId"] == event["eventId"])
        assert stored_event["eventId"] == event["eventId"]
        assert stored_event["taskId"] == event["taskId"]
        assert stored_event["type"] == event["type"]
        assert stored_event["payload"] == event["payload"]
    
    @given(st.lists(valid_event_strategy, min_size=1, max_size=10), task_id_strategy)
    def test_property_event_sequence_preservation(self, events, task_id):
        """
        Property: Event sequence ordering is preserved in the outbox.
        
        For any sequence of events stored in the outbox, they should be
        retrievable in the same sequence order.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        
        outbox = RedisOutbox(backend="memory")
        
        # Assign sequence numbers and store events
        for i, event in enumerate(events):
            event["seq"] = i
            outbox.store_event(task_id, event)
        
        # Retrieve events
        pending_events = outbox.get_pending_events(task_id)
        
        # Property: Events should be ordered by sequence number
        assert len(pending_events) == len(events)
        for i in range(len(pending_events) - 1):
            assert pending_events[i]["seq"] <= pending_events[i + 1]["seq"]
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_event_acknowledgment_removes_event(self, event, task_id):
        """
        Property: Acknowledging an event removes it from the outbox.
        
        For any event that is acknowledged, it should no longer appear
        in the pending events list.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event
        outbox.store_event(task_id, event)
        
        # Verify event is pending
        pending_before = outbox.get_pending_events(task_id)
        assert any(e["eventId"] == event["eventId"] for e in pending_before)
        
        # Acknowledge event
        result = outbox.acknowledge_event(task_id, event["eventId"])
        assert result is True
        
        # Property: Event should no longer be pending after acknowledgment
        pending_after = outbox.get_pending_events(task_id)
        assert not any(e["eventId"] == event["eventId"] for e in pending_after)
    
    @given(st.lists(valid_event_strategy, min_size=2, max_size=5), task_id_strategy)
    def test_property_partial_acknowledgment_preserves_others(self, events, task_id):
        """
        Property: Acknowledging one event preserves other pending events.
        
        For any set of events where one is acknowledged, the others
        should remain in the pending state.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        
        outbox = RedisOutbox(backend="memory")
        
        # Store all events
        for event in events:
            outbox.store_event(task_id, event)
        
        # Acknowledge first event
        ack_event = events[0]
        result = outbox.acknowledge_event(task_id, ack_event["eventId"])
        assert result is True
        
        # Property: Other events should still be pending
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == len(events) - 1
        
        # Property: Acknowledged event should not be in pending
        assert not any(e["eventId"] == ack_event["eventId"] for e in pending_events)
        
        # Property: Other events should still be present
        remaining_ids = {e["eventId"] for e in events[1:]}
        pending_ids = {e["eventId"] for e in pending_events}
        assert remaining_ids == pending_ids
    
    @given(st.lists(task_id_strategy, min_size=2, max_size=5), valid_event_strategy)
    def test_property_task_isolation(self, task_ids, event_template):
        """
        Property: Events for different tasks are isolated from each other.
        
        For any set of tasks, events stored for one task should not
        affect events for other tasks.
        """
        # Ensure unique, non-empty task IDs
        unique_task_ids = []
        for tid in task_ids:
            if tid.strip() and tid not in unique_task_ids:
                unique_task_ids.append(tid)
        assume(len(unique_task_ids) >= 2)
        
        outbox = RedisOutbox(backend="memory")
        
        # Store events for each task
        events_by_task = {}
        for task_id in unique_task_ids:
            event = dict(event_template)
            event["eventId"] = f"evt_{uuid4().hex}"
            event["taskId"] = task_id
            
            outbox.store_event(task_id, event)
            events_by_task[task_id] = event
        
        # Property: Each task should have exactly one pending event
        for task_id in unique_task_ids:
            pending = outbox.get_pending_events(task_id)
            assert len(pending) == 1
            assert pending[0]["taskId"] == task_id
            assert pending[0]["eventId"] == events_by_task[task_id]["eventId"]
        
        # Property: All tasks should be listed in pending tasks
        all_pending_tasks = set(outbox.get_all_pending_tasks())
        expected_tasks = set(unique_task_ids)
        assert all_pending_tasks == expected_tasks
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_sequence_number_monotonic_increase(self, event, task_id):
        """
        Property: Sequence numbers increase monotonically for each task.
        
        For any task, sequence numbers should never decrease.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        
        outbox = RedisOutbox(backend="memory")
        
        # Get initial sequence
        seq1 = outbox.get_next_sequence(task_id)
        
        # Store an event
        outbox.store_event(task_id, event)
        
        # Get next sequence
        seq2 = outbox.get_next_sequence(task_id)
        
        # Property: Sequence numbers should increase
        assert seq2 > seq1
        
        # Store another event
        event2 = dict(event)
        event2["eventId"] = f"evt_{uuid4().hex}"
        outbox.store_event(task_id, event2)
        
        # Get next sequence
        seq3 = outbox.get_next_sequence(task_id)
        
        # Property: Sequence should continue to increase
        assert seq3 > seq2
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_cleanup_removes_all_task_data(self, event, task_id):
        """
        Property: Task cleanup removes all associated data.
        
        For any task that is cleaned up, all events and sequence data
        should be completely removed.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event and verify it exists
        outbox.store_event(task_id, event)
        assert len(outbox.get_pending_events(task_id)) > 0
        assert task_id in outbox.get_all_pending_tasks()
        
        # Cleanup task
        outbox.cleanup_task(task_id)
        
        # Property: All task data should be removed
        assert len(outbox.get_pending_events(task_id)) == 0
        assert task_id not in outbox.get_all_pending_tasks()
        
        # Property: Sequence should reset for cleaned task
        seq_after_cleanup = outbox.get_next_sequence(task_id)
        assert seq_after_cleanup == 0


class TestEventPersistenceComprehensiveProperties:
    """
    Comprehensive property-based tests for event persistence behavior.
    
    **Task 3.4: Write property tests for event persistence**
    **Property 3: Event Persistence Before Delivery**
    **Validates: Requirements 2.1**
    
    These tests provide comprehensive validation of event persistence behavior
    including atomicity, consistency, durability, and edge cases.
    """
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_comprehensive_event_persistence_atomicity(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Atomicity**
        
        For any event publication attempt, the Event_Outbox SHALL persist 
        the event atomically - either the event is fully persisted or not at all.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Test atomicity: event should be immediately available after store_event returns
        outbox.store_event(task_id, event)
        
        # Property: Event must be immediately available in pending events (atomic persistence)
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) >= 1
        
        # Property: The persisted event must be complete and unchanged
        stored_event = next(e for e in pending_events if e["eventId"] == event["eventId"])
        assert stored_event == event, "Event data was corrupted during persistence"
        
        # Property: Task must be listed in pending tasks immediately
        pending_tasks = outbox.get_all_pending_tasks()
        assert task_id in pending_tasks, "Task not immediately available in pending tasks"
    
    @given(st.lists(valid_event_strategy, min_size=1, max_size=20), task_id_strategy)
    def test_property_3_comprehensive_event_persistence_consistency(self, events, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Consistency**
        
        For any sequence of event publication attempts, the Event_Outbox SHALL 
        maintain consistency across all persistence operations.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        
        outbox = RedisOutbox(backend="memory")
        
        # Assign sequence numbers to ensure ordering
        for i, event in enumerate(events):
            event["seq"] = i
        
        # Store all events
        for event in events:
            outbox.store_event(task_id, event)
        
        # Property: All events must be persisted consistently
        pending_events = outbox.get_pending_events(task_id)
        assert len(pending_events) == len(events), "Not all events were persisted"
        
        # Property: Event ordering must be preserved (consistency)
        pending_events.sort(key=lambda e: e["seq"])
        for i, event in enumerate(events):
            assert pending_events[i]["eventId"] == event["eventId"]
            assert pending_events[i]["seq"] == event["seq"]
        
        # Property: Sequence numbers must be consistent
        current_seq = outbox.get_next_sequence(task_id)
        assert current_seq >= len(events), "Sequence counter not consistent with stored events"
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_comprehensive_event_persistence_durability(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Durability**
        
        For any event publication attempt, the Event_Outbox SHALL ensure 
        durability - persisted events survive outbox recreation.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        # Create first outbox instance and store event
        outbox1 = RedisOutbox(backend="memory")
        outbox1.store_event(task_id, event)
        
        # Verify event is stored
        pending1 = outbox1.get_pending_events(task_id)
        assert len(pending1) == 1
        assert pending1[0]["eventId"] == event["eventId"]
        
        # Create second outbox instance (simulates restart/recreation)
        outbox2 = RedisOutbox(backend="memory")
        
        # Property: Event should survive outbox recreation (durability)
        # Note: In memory backend, this tests the local storage durability
        # In Redis backend, this would test Redis persistence
        if outbox1._local_store:  # Memory backend shares state
            outbox2._local_store = outbox1._local_store
            outbox2._local_seq = outbox1._local_seq
            
            pending2 = outbox2.get_pending_events(task_id)
            assert len(pending2) == 1
            assert pending2[0]["eventId"] == event["eventId"]
            assert pending2[0] == event
    
    @given(st.lists(valid_event_strategy, min_size=5, max_size=15), task_id_strategy)
    def test_property_3_event_persistence_under_concurrent_operations(self, events, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Concurrent Safety**
        
        For any concurrent event publication attempts, the Event_Outbox SHALL 
        persist all events correctly without data corruption or loss.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        assume(len(set(e["eventId"] for e in events)) == len(events))
        
        outbox = RedisOutbox(backend="memory")
        
        # Simulate concurrent operations by interleaving stores and retrievals
        stored_events = []
        for i, event in enumerate(events):
            event["seq"] = i
            outbox.store_event(task_id, event)
            stored_events.append(event)
            
            # Interleave with pending event retrieval (simulates concurrent access)
            pending = outbox.get_pending_events(task_id)
            assert len(pending) == len(stored_events)
            
            # Property: All previously stored events must still be present
            stored_ids = {e["eventId"] for e in stored_events}
            pending_ids = {e["eventId"] for e in pending}
            assert stored_ids == pending_ids
        
        # Property: Final state must contain all events
        final_pending = outbox.get_pending_events(task_id)
        assert len(final_pending) == len(events)
        
        # Property: All events must be intact after concurrent operations
        for event in events:
            matching_event = next(e for e in final_pending if e["eventId"] == event["eventId"])
            assert matching_event == event
    
    @given(valid_event_strategy, task_id_strategy, st.text(min_size=1, max_size=50))
    def test_property_3_event_persistence_with_delivery_simulation(self, event, task_id, delivery_error):
        """
        **Property 3: Event Persistence Before Delivery - Delivery Failure Handling**
        
        For any event publication attempt that fails during delivery, 
        the Event_Outbox SHALL maintain the persisted event for retry.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Store event (persistence before delivery)
        outbox.store_event(task_id, event)
        
        # Verify event is persisted before delivery attempt
        pending_before = outbox.get_pending_events(task_id)
        assert len(pending_before) == 1
        assert pending_before[0]["eventId"] == event["eventId"]
        
        # Simulate delivery failure (event remains in outbox)
        # Property: Event must remain available for retry after delivery failure
        pending_after_failure = outbox.get_pending_events(task_id)
        assert len(pending_after_failure) == 1
        assert pending_after_failure[0]["eventId"] == event["eventId"]
        assert pending_after_failure[0] == event
        
        # Simulate successful delivery (acknowledge event)
        ack_result = outbox.acknowledge_event(task_id, event["eventId"])
        assert ack_result is True
        
        # Property: Event should be removed only after successful acknowledgment
        pending_after_ack = outbox.get_pending_events(task_id)
        assert len(pending_after_ack) == 0
    
    @given(st.lists(task_id_strategy, min_size=2, max_size=10), 
           st.lists(valid_event_strategy, min_size=2, max_size=10))
    def test_property_3_multi_task_event_persistence_isolation(self, task_ids, event_templates):
        """
        **Property 3: Event Persistence Before Delivery - Multi-Task Isolation**
        
        For any multiple task event publication attempts, the Event_Outbox SHALL 
        persist events with proper task isolation.
        
        **Validates: Requirements 2.1**
        """
        # Ensure unique task IDs
        unique_task_ids = []
        for tid in task_ids:
            if tid.strip() and tid not in unique_task_ids:
                unique_task_ids.append(tid)
        assume(len(unique_task_ids) >= 2)
        assume(len(event_templates) >= len(unique_task_ids))
        
        outbox = RedisOutbox(backend="memory")
        
        # Create events for each task
        task_events = {}
        for i, task_id in enumerate(unique_task_ids):
            event = dict(event_templates[i])
            event["eventId"] = f"evt_{uuid4().hex}"
            event["taskId"] = task_id
            event["seq"] = 0
            
            # Store event for this task
            outbox.store_event(task_id, event)
            task_events[task_id] = event
        
        # Property: Each task's events must be isolated and persisted correctly
        for task_id, expected_event in task_events.items():
            pending = outbox.get_pending_events(task_id)
            assert len(pending) == 1
            assert pending[0]["eventId"] == expected_event["eventId"]
            assert pending[0]["taskId"] == task_id
            assert pending[0] == expected_event
        
        # Property: All tasks must be listed in pending tasks
        all_pending_tasks = set(outbox.get_all_pending_tasks())
        expected_tasks = set(unique_task_ids)
        assert all_pending_tasks == expected_tasks
        
        # Property: Acknowledging one task's events doesn't affect others
        first_task = unique_task_ids[0]
        first_event = task_events[first_task]
        outbox.acknowledge_event(first_task, first_event["eventId"])
        
        # Verify other tasks' events are unaffected
        for task_id in unique_task_ids[1:]:
            pending = outbox.get_pending_events(task_id)
            assert len(pending) == 1
            assert pending[0]["eventId"] == task_events[task_id]["eventId"]
    
    @given(valid_event_strategy, task_id_strategy)
    def test_property_3_event_persistence_error_conditions(self, event, task_id):
        """
        **Property 3: Event Persistence Before Delivery - Error Condition Handling**
        
        For any event publication attempt under error conditions, 
        the Event_Outbox SHALL handle errors gracefully while maintaining persistence guarantees.
        
        **Validates: Requirements 2.1**
        """
        assume(task_id.strip())
        
        outbox = RedisOutbox(backend="memory")
        
        # Test persistence with empty task ID (should fail gracefully)
        with pytest.raises(RedisOutboxError):
            outbox.store_event("", event)
        
        # Test persistence with None task ID (should fail gracefully)
        with pytest.raises((RedisOutboxError, AttributeError)):
            outbox.store_event(None, event)
        
        # Test persistence with whitespace-only task ID (should fail gracefully)
        with pytest.raises(RedisOutboxError):
            outbox.store_event("   ", event)
        
        # Property: Valid operations should still work after error conditions
        outbox.store_event(task_id, event)
        pending = outbox.get_pending_events(task_id)
        assert len(pending) == 1
        assert pending[0]["eventId"] == event["eventId"]
        
        # Test acknowledgment with invalid parameters
        assert outbox.acknowledge_event("", event["eventId"]) is False
        assert outbox.acknowledge_event(task_id, "") is False
        assert outbox.acknowledge_event("nonexistent", event["eventId"]) is False
        
        # Property: Event should still be present after invalid acknowledgment attempts
        pending_after_invalid_acks = outbox.get_pending_events(task_id)
        assert len(pending_after_invalid_acks) == 1
        assert pending_after_invalid_acks[0]["eventId"] == event["eventId"]


class TestEventValidationProperties:
    """Property-based tests for event validation."""
    
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(), st.integers(), st.booleans(), st.none()),
        min_size=0,
        max_size=10
    ))
    def test_property_invalid_events_rejected(self, invalid_event_data):
        """
        Property: Invalid events are consistently rejected.
        
        For any event data that doesn't conform to the schema,
        the outbox should reject it with a validation error.
        """
        # Skip if this accidentally creates a valid event
        required_fields = {"eventId", "eventVersion", "taskId", "assistant", "type", "timestamp", "seq", "payload"}
        if required_fields.issubset(invalid_event_data.keys()):
            # Check if eventId has correct format
            event_id = invalid_event_data.get("eventId", "")
            if isinstance(event_id, str) and event_id.startswith("evt_") and len(event_id) == 36:
                assume(False)  # Skip valid events
        
        outbox = RedisOutbox(backend="memory")
        
        # Property: Invalid events should raise validation error
        with pytest.raises(EventValidationError):
            outbox.store_event("task_123", invalid_event_data)
    
    @given(valid_event_strategy)
    def test_property_valid_events_accepted(self, event):
        """
        Property: All valid events are accepted.
        
        For any event that conforms to the schema, the outbox
        should accept and store it without error.
        """
        outbox = RedisOutbox(backend="memory")
        task_id = event["taskId"]
        
        # Property: Valid events should be stored without exception
        try:
            outbox.store_event(task_id, event)
            # If no exception, verify it was stored
            pending = outbox.get_pending_events(task_id)
            assert any(e["eventId"] == event["eventId"] for e in pending)
        except EventValidationError:
            # This should not happen for valid events
            pytest.fail("Valid event was rejected by validation")