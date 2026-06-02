"""
Property-based tests for Event Recovery Service.

These tests validate universal properties that should hold across all valid executions,
specifically focusing on Requirements 2.3 and 2.6 (event recovery and sequence continuity).
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock
from uuid import uuid4

from client.control_plane_client import ControlPlaneClient, PublishEventResult
from outbox.redis_outbox import RedisOutbox
from outbox.recovery_service import EventRecoveryService, RecoveryConfig


# Strategy for generating valid event IDs
event_id_strategy = st.builds(lambda: f"evt_{uuid4().hex}")

# Strategy for generating valid timestamps
timestamp_strategy = st.builds(
    lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
)

# Strategy for generating task IDs
task_id_strategy = st.text(
    min_size=1, 
    max_size=50, 
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))
)

# Strategy for generating valid events
valid_event_strategy = st.builds(
    dict,
    eventId=event_id_strategy,
    eventVersion=st.integers(min_value=1, max_value=10),
    taskId=task_id_strategy,
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


class TestEventRecoveryProperties:
    """
    Property-based tests for event recovery behavior.
    
    **Validates: Requirements 2.3, 2.6**
    
    These tests verify that event recovery works correctly across all scenarios
    and maintains sequence continuity across Python Agent restarts.
    """
    
    @given(st.lists(valid_event_strategy, min_size=1, max_size=10), task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_5_event_recovery_after_restart(self, events, task_id):
        """
        **Property 5: Event Recovery After Restart**
        
        For any Python_Agent restart scenario, all unacknowledged events 
        in the Event_Outbox SHALL be recovered and redelivered.
        
        **Validates: Requirements 2.3**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        
        # Setup: Create outbox with pending events (simulating pre-restart state)
        outbox = RedisOutbox(backend="memory")
        
        # Assign task ID and sequence numbers to events
        for i, event in enumerate(events):
            event["taskId"] = task_id
            event["seq"] = i
            outbox.store_event(task_id, event)
        
        # Verify events are pending before recovery
        pending_before = outbox.get_pending_events(task_id)
        assert len(pending_before) == len(events)
        
        # Setup mock client for successful delivery
        mock_client = Mock(spec=ControlPlaneClient)
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        mock_client.publish_event_with_retry_result.return_value = success_result
        
        # Create recovery service (simulating agent restart)
        config = RecoveryConfig(enabled=True, startup_delay_seconds=0.0)
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Property: All pending events must be recovered and redelivered
        assert stats.total_events_found == len(events)
        assert stats.successful_deliveries == len(events)
        assert stats.failed_deliveries == 0
        
        # Property: All events must be delivered via client
        assert mock_client.publish_event_with_retry_result.call_count == len(events)
        
        # Property: All events must be acknowledged and removed from outbox
        pending_after = outbox.get_pending_events(task_id)
        assert len(pending_after) == 0
        
        # Property: Recovery must complete successfully
        assert stats.tasks_with_failures == 0
    
    @given(st.lists(valid_event_strategy, min_size=2, max_size=10), task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_8_event_sequence_continuity(self, events, task_id):
        """
        **Property 8: Event Sequence Continuity**
        
        For any Python_Agent restart, event sequence numbers SHALL maintain 
        continuity without gaps or duplicates.
        
        **Validates: Requirements 2.6**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        assume(len(events) >= 2)  # Need at least 2 events for continuity testing
        
        # Setup: Create events with continuous sequence numbers
        outbox = RedisOutbox(backend="memory")
        
        for i, event in enumerate(events):
            event["taskId"] = task_id
            event["seq"] = i  # Continuous sequence: 0, 1, 2, 3, ...
            outbox.store_event(task_id, event)
        
        # Setup mock client
        mock_client = Mock(spec=ControlPlaneClient)
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        mock_client.publish_event_with_retry_result.return_value = success_result
        
        # Create recovery service with sequence gap detection enabled
        config = RecoveryConfig(
            enabled=True, 
            startup_delay_seconds=0.0,
            sequence_gap_detection=True
        )
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Property: No sequence gaps should be detected for continuous sequences
        assert stats.sequence_gaps_detected == 0
        assert stats.sequence_gaps_resolved == 0
        
        # Property: All events should be recovered successfully
        assert stats.successful_deliveries == len(events)
        assert stats.failed_deliveries == 0
        
        # Property: Events should be delivered in sequence order
        call_args_list = mock_client.publish_event_with_retry_result.call_args_list
        delivered_sequences = []
        for call_args in call_args_list:
            event = call_args[0][1]  # Second argument is the event
            delivered_sequences.append(event["seq"])
        
        # Sequences should be in ascending order (continuity maintained)
        assert delivered_sequences == sorted(delivered_sequences)
        assert delivered_sequences == list(range(len(events)))
    
    @given(st.lists(valid_event_strategy, min_size=3, max_size=8), task_id_strategy)
    def test_property_sequence_gap_detection_and_resolution(self, events, task_id):
        """
        Property: Sequence gaps are correctly detected and resolved during recovery.
        
        For any set of events with sequence gaps, the recovery service should
        detect the gaps and handle them appropriately.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        assume(len(events) >= 3)  # Need enough events to create meaningful gaps
        
        # Setup: Create events with intentional sequence gaps
        outbox = RedisOutbox(backend="memory")
        
        # Create gaps by using non-continuous sequence numbers
        # Example: [0, 1, 4, 7] instead of [0, 1, 2, 3]
        gap_sequences = []
        for i in range(len(events)):
            seq = i * 2 + (i // 2)  # Creates gaps: 0, 2, 5, 8, 12, ...
            gap_sequences.append(seq)
        
        for i, event in enumerate(events):
            event["taskId"] = task_id
            event["seq"] = gap_sequences[i]
            outbox.store_event(task_id, event)
        
        # Setup mock client
        mock_client = Mock(spec=ControlPlaneClient)
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        mock_client.publish_event_with_retry_result.return_value = success_result
        
        # Create recovery service with gap detection enabled
        config = RecoveryConfig(
            enabled=True, 
            startup_delay_seconds=0.0,
            sequence_gap_detection=True
        )
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Property: Gaps should be detected
        expected_gaps = sum(gap_sequences[i] - gap_sequences[i-1] - 1 
                          for i in range(1, len(gap_sequences)) 
                          if gap_sequences[i] > gap_sequences[i-1] + 1)
        
        if expected_gaps > 0:
            assert stats.sequence_gaps_detected > 0
            assert stats.sequence_gaps_resolved == stats.sequence_gaps_detected
        
        # Property: All events should still be recovered despite gaps
        assert stats.successful_deliveries == len(events)
        assert stats.failed_deliveries == 0
    
    @given(st.lists(task_id_strategy, min_size=2, max_size=5), valid_event_strategy)
    def test_property_multi_task_recovery_isolation(self, task_ids, event_template):
        """
        Property: Recovery of events for multiple tasks maintains isolation.
        
        For any set of tasks with pending events, recovery should process
        each task independently without cross-contamination.
        """
        # Ensure unique, non-empty task IDs
        unique_task_ids = []
        for tid in task_ids:
            if tid.strip() and tid not in unique_task_ids:
                unique_task_ids.append(tid)
        assume(len(unique_task_ids) >= 2)
        
        # Setup: Create events for each task
        outbox = RedisOutbox(backend="memory")
        events_by_task = {}
        
        for task_id in unique_task_ids:
            # Create 2 events per task
            task_events = []
            for i in range(2):
                event = dict(event_template)
                event["eventId"] = f"evt_{uuid4().hex}"
                event["taskId"] = task_id
                event["seq"] = i
                event["type"] = f"TASK_EVENT_{i}"
                
                outbox.store_event(task_id, event)
                task_events.append(event)
            
            events_by_task[task_id] = task_events
        
        # Setup mock client
        mock_client = Mock(spec=ControlPlaneClient)
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        mock_client.publish_event_with_retry_result.return_value = success_result
        
        # Create recovery service
        config = RecoveryConfig(enabled=True, startup_delay_seconds=0.0)
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Property: All tasks should be processed
        assert stats.total_tasks_scanned == len(unique_task_ids)
        assert stats.total_events_found == len(unique_task_ids) * 2
        assert stats.successful_deliveries == len(unique_task_ids) * 2
        
        # Property: Each task's events should be delivered correctly
        call_args_list = mock_client.publish_event_with_retry_result.call_args_list
        delivered_by_task = {}
        
        for call_args in call_args_list:
            task_id = call_args[0][0]  # First argument is task_id
            event = call_args[0][1]    # Second argument is event
            
            if task_id not in delivered_by_task:
                delivered_by_task[task_id] = []
            delivered_by_task[task_id].append(event)
        
        # Property: Each task should have exactly its events delivered
        for task_id in unique_task_ids:
            assert task_id in delivered_by_task
            delivered_events = delivered_by_task[task_id]
            assert len(delivered_events) == 2
            
            # All delivered events should belong to the correct task
            for event in delivered_events:
                assert event["taskId"] == task_id
        
        # Property: No events should remain in outbox after recovery
        for task_id in unique_task_ids:
            remaining = outbox.get_pending_events(task_id)
            assert len(remaining) == 0
    
    @given(st.lists(valid_event_strategy, min_size=1, max_size=5), task_id_strategy, st.integers(min_value=1, max_value=3))
    def test_property_partial_recovery_resilience(self, events, task_id, failure_count):
        """
        Property: Recovery handles partial failures gracefully.
        
        For any set of events where some deliveries fail, the recovery
        should succeed for deliverable events and leave failed events
        in the outbox for future recovery attempts.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        assume(failure_count < len(events))  # Some events should succeed
        
        # Setup events in outbox
        outbox = RedisOutbox(backend="memory")
        
        for i, event in enumerate(events):
            event["taskId"] = task_id
            event["seq"] = i
            outbox.store_event(task_id, event)
        
        # Setup mock client with mixed success/failure results
        mock_client = Mock(spec=ControlPlaneClient)
        
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        
        failure_result = PublishEventResult(
            response=None,
            attempts=2,
            total_delay_seconds=1.0,
            circuit_breaker_triggered=False,
            final_error=Exception("Delivery failed")
        )
        
        # First failure_count events fail, rest succeed
        results = [failure_result] * failure_count + [success_result] * (len(events) - failure_count)
        mock_client.publish_event_with_retry_result.side_effect = results
        
        # Create recovery service
        config = RecoveryConfig(enabled=True, startup_delay_seconds=0.0)
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Property: Correct number of successes and failures
        expected_successes = len(events) - failure_count
        expected_failures = failure_count
        
        assert stats.successful_deliveries == expected_successes
        assert stats.failed_deliveries == expected_failures
        assert stats.total_events_found == len(events)
        
        # Property: Failed events should remain in outbox
        remaining_events = outbox.get_pending_events(task_id)
        assert len(remaining_events) == failure_count
        
        # Property: Remaining events should be the ones that failed
        remaining_event_ids = {e["eventId"] for e in remaining_events}
        failed_event_ids = {events[i]["eventId"] for i in range(failure_count)}
        assert remaining_event_ids == failed_event_ids
        
        # Property: If any failures occurred, task should be marked as having failures
        if failure_count > 0:
            assert stats.tasks_with_failures == 1
        else:
            assert stats.tasks_with_failures == 0
    
    @given(st.integers(min_value=1, max_value=10), st.integers(min_value=1, max_value=5))
    def test_property_batch_processing_completeness(self, total_tasks, batch_size):
        """
        Property: Batch processing handles all tasks regardless of batch size.
        
        For any number of tasks and any batch size, all tasks should be
        processed during recovery.
        """
        assume(batch_size <= total_tasks)  # Batch size should be reasonable
        
        # Setup: Create tasks with no events (for simplicity)
        task_ids = [f"task_{i}" for i in range(total_tasks)]
        
        outbox = Mock(spec=RedisOutbox)
        outbox.get_all_pending_tasks.return_value = task_ids
        outbox.get_pending_events.return_value = []  # No events per task
        outbox.acknowledge_event.return_value = True
        
        mock_client = Mock(spec=ControlPlaneClient)
        
        # Create recovery service with specified batch size
        config = RecoveryConfig(
            enabled=True, 
            startup_delay_seconds=0.0,
            batch_size=batch_size
        )
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Property: All tasks should be scanned regardless of batch size
        assert stats.total_tasks_scanned == total_tasks
        
        # Property: get_pending_events should be called for each task
        assert outbox.get_pending_events.call_count == total_tasks
        
        # Property: Each task should be processed exactly once
        processed_task_ids = []
        for call_args in outbox.get_pending_events.call_args_list:
            task_id = call_args[0][0]  # First argument is task_id
            processed_task_ids.append(task_id)
        
        assert sorted(processed_task_ids) == sorted(task_ids)
        assert len(set(processed_task_ids)) == total_tasks  # No duplicates
    
    @given(st.lists(valid_event_strategy, min_size=1, max_size=5), task_id_strategy)
    def test_property_recovery_idempotency(self, events, task_id):
        """
        Property: Multiple recovery attempts are idempotent.
        
        For any set of events, running recovery multiple times should
        not cause duplicate deliveries or other side effects.
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(len(set(e["eventId"] for e in events)) == len(events))  # Unique event IDs
        
        # Setup events in outbox
        outbox = RedisOutbox(backend="memory")
        
        for i, event in enumerate(events):
            event["taskId"] = task_id
            event["seq"] = i
            outbox.store_event(task_id, event)
        
        # Setup mock client
        mock_client = Mock(spec=ControlPlaneClient)
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        mock_client.publish_event_with_retry_result.return_value = success_result
        
        # Create recovery service
        config = RecoveryConfig(enabled=True, startup_delay_seconds=0.0)
        service = EventRecoveryService(outbox=outbox, client=mock_client, config=config)
        
        # Perform first recovery
        stats1 = service.recover_events_now()
        
        # Reset mock call count
        mock_client.reset_mock()
        
        # Perform second recovery
        stats2 = service.recover_events_now()
        
        # Property: First recovery should process all events
        assert stats1.total_events_found == len(events)
        assert stats1.successful_deliveries == len(events)
        
        # Property: Second recovery should find no events (idempotent)
        assert stats2.total_events_found == 0
        assert stats2.successful_deliveries == 0
        
        # Property: Client should not be called during second recovery
        assert mock_client.publish_event_with_retry_result.call_count == 0
        
        # Property: No events should remain in outbox
        remaining = outbox.get_pending_events(task_id)
        assert len(remaining) == 0