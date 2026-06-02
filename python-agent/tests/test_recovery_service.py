"""
Unit tests for Event Recovery Service.

Tests cover event recovery after Python Agent restart, sequence continuity,
and integration with Redis outbox and enhanced client.
"""

from __future__ import annotations

import pytest
import threading
import time
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from client.control_plane_client import ControlPlaneClient, PublishEventResult
from outbox.redis_outbox import RedisOutbox
from outbox.recovery_service import (
    EventRecoveryService,
    RecoveryConfig,
    RecoveryStats,
    create_recovery_service,
)


@pytest.fixture
def mock_outbox():
    """Create a mock Redis outbox for testing."""
    outbox = Mock(spec=RedisOutbox)
    outbox.get_all_pending_tasks.return_value = []
    outbox.get_pending_events.return_value = []
    outbox.acknowledge_event.return_value = True
    return outbox


@pytest.fixture
def mock_client():
    """Create a mock Control Plane client for testing."""
    client = Mock(spec=ControlPlaneClient)
    
    # Mock successful event delivery
    success_result = PublishEventResult(
        response={"ok": True},
        attempts=1,
        total_delay_seconds=0.0,
        circuit_breaker_triggered=False,
        final_error=None
    )
    client.publish_event_with_retry_result.return_value = success_result
    
    return client


@pytest.fixture
def recovery_config():
    """Create a test recovery configuration."""
    return RecoveryConfig(
        enabled=True,
        startup_delay_seconds=0.1,  # Short delay for testing
        max_retry_attempts=2,
        retry_backoff_seconds=0.1,
        batch_size=5,
        recovery_timeout_seconds=10.0,
        sequence_gap_detection=True,
        metrics_enabled=True,
    )


@pytest.fixture
def sample_events():
    """Create sample events for testing."""
    base_time = datetime.now(timezone.utc)
    
    events = []
    for i in range(3):
        event = {
            "eventId": f"evt_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": "task_123",
            "assistant": "ai-agent",
            "type": f"EVENT_{i}",
            "timestamp": base_time.isoformat().replace("+00:00", "Z"),
            "seq": i,
            "payload": {"message": f"Event {i}"}
        }
        events.append(event)
    
    return events


class TestEventRecoveryService:
    """Test cases for EventRecoveryService."""
    
    def test_initialization(self, mock_outbox, mock_client, recovery_config):
        """Test recovery service initialization."""
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        assert service.outbox is mock_outbox
        assert service.client is mock_client
        assert service.config is recovery_config
        assert not service._recovery_active
        assert service._recovery_stats is None
    
    def test_factory_function(self, mock_client):
        """Test factory function for creating recovery service."""
        service = create_recovery_service(client=mock_client)
        
        assert service.client is mock_client
        assert isinstance(service.outbox, RedisOutbox)
        assert isinstance(service.config, RecoveryConfig)
    
    def test_factory_function_requires_client(self):
        """Test that factory function requires client parameter."""
        with pytest.raises(ValueError, match="ControlPlaneClient is required"):
            create_recovery_service(client=None)
    
    def test_disabled_service(self, mock_outbox, mock_client):
        """Test that disabled service does not start recovery."""
        config = RecoveryConfig(enabled=False)
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=config
        )
        
        service.start_recovery_service()
        time.sleep(0.1)  # Give time for thread to start
        
        assert service._recovery_thread is None
        mock_outbox.get_all_pending_tasks.assert_not_called()
    
    def test_no_pending_events_recovery(self, mock_outbox, mock_client, recovery_config):
        """Test recovery when no pending events exist."""
        mock_outbox.get_all_pending_tasks.return_value = []
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 0
        assert stats.total_events_found == 0
        assert stats.successful_deliveries == 0
        assert stats.failed_deliveries == 0
        assert stats.recovery_duration_seconds > 0
        
        mock_outbox.get_all_pending_tasks.assert_called_once()
    
    def test_successful_event_recovery(self, mock_outbox, mock_client, recovery_config, sample_events):
        """Test successful recovery of pending events."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = sample_events
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 1
        assert stats.total_events_found == 3
        assert stats.successful_deliveries == 3
        assert stats.failed_deliveries == 0
        assert stats.tasks_with_failures == 0
        
        # Verify all events were delivered
        assert mock_client.publish_event_with_retry_result.call_count == 3
        
        # Verify all events were acknowledged
        assert mock_outbox.acknowledge_event.call_count == 3
        for event in sample_events:
            mock_outbox.acknowledge_event.assert_any_call(task_id, event["eventId"])
    
    def test_failed_event_recovery(self, mock_outbox, mock_client, recovery_config, sample_events):
        """Test recovery when event delivery fails."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = sample_events
        
        # Mock failed delivery
        failed_result = PublishEventResult(
            response=None,
            attempts=2,
            total_delay_seconds=1.0,
            circuit_breaker_triggered=False,
            final_error=Exception("Delivery failed")
        )
        mock_client.publish_event_with_retry_result.return_value = failed_result
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 1
        assert stats.total_events_found == 3
        assert stats.successful_deliveries == 0
        assert stats.failed_deliveries == 3
        assert stats.tasks_with_failures == 1
        
        # Verify events were not acknowledged (kept in outbox)
        mock_outbox.acknowledge_event.assert_not_called()
    
    def test_mixed_success_failure_recovery(self, mock_outbox, mock_client, recovery_config, sample_events):
        """Test recovery with mixed success and failure results."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = sample_events
        
        # Mock mixed results - first succeeds, others fail
        success_result = PublishEventResult(
            response={"ok": True},
            attempts=1,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=False,
            final_error=None
        )
        failed_result = PublishEventResult(
            response=None,
            attempts=2,
            total_delay_seconds=1.0,
            circuit_breaker_triggered=False,
            final_error=Exception("Delivery failed")
        )
        
        mock_client.publish_event_with_retry_result.side_effect = [
            success_result, failed_result, failed_result
        ]
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 1
        assert stats.total_events_found == 3
        assert stats.successful_deliveries == 1
        assert stats.failed_deliveries == 2
        assert stats.tasks_with_failures == 1
        
        # Verify only successful event was acknowledged
        mock_outbox.acknowledge_event.assert_called_once_with(task_id, sample_events[0]["eventId"])
    
    def test_multiple_tasks_recovery(self, mock_outbox, mock_client, recovery_config):
        """Test recovery across multiple tasks."""
        task_ids = ["task_1", "task_2", "task_3"]
        mock_outbox.get_all_pending_tasks.return_value = task_ids
        
        # Each task has 2 events
        events_per_task = []
        for i, task_id in enumerate(task_ids):
            task_events = []
            for j in range(2):
                event = {
                    "eventId": f"evt_{uuid4().hex}",
                    "eventVersion": 1,
                    "taskId": task_id,
                    "assistant": "ai-agent",
                    "type": f"EVENT_{j}",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "seq": j,
                    "payload": {"message": f"Task {i} Event {j}"}
                }
                task_events.append(event)
            events_per_task.append(task_events)
        
        mock_outbox.get_pending_events.side_effect = events_per_task
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 3
        assert stats.total_events_found == 6  # 2 events per task
        assert stats.successful_deliveries == 6
        assert stats.failed_deliveries == 0
        
        # Verify all tasks were processed
        assert mock_outbox.get_pending_events.call_count == 3
        for task_id in task_ids:
            mock_outbox.get_pending_events.assert_any_call(task_id)
    
    def test_batch_processing(self, mock_outbox, mock_client):
        """Test that tasks are processed in batches."""
        # Create config with small batch size
        config = RecoveryConfig(
            enabled=True,
            startup_delay_seconds=0.0,
            batch_size=2,  # Small batch size
        )
        
        # Create 5 tasks (will require 3 batches)
        task_ids = [f"task_{i}" for i in range(5)]
        mock_outbox.get_all_pending_tasks.return_value = task_ids
        mock_outbox.get_pending_events.return_value = []  # No events for simplicity
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 5
        # All tasks should be processed despite batching
        assert mock_outbox.get_pending_events.call_count == 5
    
    def test_sequence_gap_detection(self, mock_outbox, mock_client, recovery_config):
        """Test detection and resolution of sequence gaps."""
        task_id = "task_123"
        
        # Create events with sequence gap (0, 1, 4, 5) - missing 2, 3
        events_with_gaps = []
        for seq in [0, 1, 4, 5]:
            event = {
                "eventId": f"evt_{uuid4().hex}",
                "eventVersion": 1,
                "taskId": task_id,
                "assistant": "ai-agent",
                "type": f"EVENT_{seq}",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "seq": seq,
                "payload": {"message": f"Event {seq}"}
            }
            events_with_gaps.append(event)
        
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = events_with_gaps
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.sequence_gaps_detected == 2  # Missing sequences 2 and 3
        assert stats.sequence_gaps_resolved == 2  # Both gaps "resolved" (accepted)
        assert stats.successful_deliveries == 4  # All events delivered
    
    def test_sequence_gap_detection_disabled(self, mock_outbox, mock_client):
        """Test that sequence gap detection can be disabled."""
        config = RecoveryConfig(
            enabled=True,
            startup_delay_seconds=0.0,
            sequence_gap_detection=False,  # Disabled
        )
        
        task_id = "task_123"
        events_with_gaps = [
            {
                "eventId": f"evt_{uuid4().hex}",
                "eventVersion": 1,
                "taskId": task_id,
                "assistant": "ai-agent",
                "type": "EVENT_0",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "seq": 0,
                "payload": {"message": "Event 0"}
            },
            {
                "eventId": f"evt_{uuid4().hex}",
                "eventVersion": 1,
                "taskId": task_id,
                "assistant": "ai-agent",
                "type": "EVENT_5",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "seq": 5,  # Gap from 0 to 5
                "payload": {"message": "Event 5"}
            }
        ]
        
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = events_with_gaps
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=config
        )
        
        stats = service.recover_events_now()
        
        # No gap detection should occur
        assert stats.sequence_gaps_detected == 0
        assert stats.sequence_gaps_resolved == 0
        assert stats.successful_deliveries == 2
    
    def test_background_service_lifecycle(self, mock_outbox, mock_client, recovery_config):
        """Test starting and stopping the background recovery service."""
        mock_outbox.get_all_pending_tasks.return_value = []
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        # Start service
        service.start_recovery_service()
        assert service._recovery_thread is not None
        assert service._recovery_thread.is_alive()
        
        # Wait for recovery to complete
        time.sleep(0.2)
        
        # Stop service
        stopped = service.stop_recovery_service(timeout_seconds=1.0)
        assert stopped is True
        assert not service._recovery_thread.is_alive()
    
    def test_background_service_already_running(self, mock_outbox, mock_client, recovery_config):
        """Test that starting an already running service is handled gracefully."""
        mock_outbox.get_all_pending_tasks.return_value = []
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        # Start service twice
        service.start_recovery_service()
        first_thread = service._recovery_thread
        
        service.start_recovery_service()  # Should not create new thread
        assert service._recovery_thread is first_thread
        
        # Cleanup
        service.stop_recovery_service()
    
    def test_recovery_callbacks(self, mock_outbox, mock_client, recovery_config, sample_events):
        """Test recovery callbacks for monitoring and testing."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = sample_events
        
        # Setup callbacks
        on_start_called = threading.Event()
        on_complete_called = threading.Event()
        recovered_events = []
        
        def on_start():
            on_start_called.set()
        
        def on_complete(stats):
            on_complete_called.set()
        
        def on_event_recovered(task_id, event):
            recovered_events.append((task_id, event["eventId"]))
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        service.set_recovery_callbacks(
            on_start=on_start,
            on_complete=on_complete,
            on_event_recovered=on_event_recovered
        )
        
        stats = service.recover_events_now()
        
        # Verify callbacks were called
        assert on_start_called.is_set()
        assert on_complete_called.is_set()
        assert len(recovered_events) == 3
        
        # Verify event recovery callbacks
        for i, (cb_task_id, cb_event_id) in enumerate(recovered_events):
            assert cb_task_id == task_id
            assert cb_event_id == sample_events[i]["eventId"]
    
    def test_service_metrics(self, mock_outbox, mock_client, recovery_config, sample_events):
        """Test service metrics collection."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = sample_events
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        # Initial metrics
        initial_metrics = service.get_service_metrics()
        assert initial_metrics["total_recoveries"] == 0
        assert initial_metrics["successful_recoveries"] == 0
        assert initial_metrics["total_events_recovered"] == 0
        
        # Perform recovery
        stats = service.recover_events_now()
        
        # Check updated metrics
        updated_metrics = service.get_service_metrics()
        assert updated_metrics["total_recoveries"] == 1
        assert updated_metrics["successful_recoveries"] == 1
        assert updated_metrics["total_events_recovered"] == 3
        assert updated_metrics["lastRecoveryStats"] is not None
    
    def test_circuit_breaker_triggered_recovery(self, mock_outbox, mock_client, recovery_config, sample_events):
        """Test recovery when circuit breaker is triggered."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        mock_outbox.get_pending_events.return_value = sample_events
        
        # Mock circuit breaker triggered result
        cb_result = PublishEventResult(
            response=None,
            attempts=0,
            total_delay_seconds=0.0,
            circuit_breaker_triggered=True,
            final_error=Exception("Circuit breaker open")
        )
        mock_client.publish_event_with_retry_result.return_value = cb_result
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        stats = service.recover_events_now()
        
        assert stats.total_events_found == 3
        assert stats.successful_deliveries == 0
        assert stats.failed_deliveries == 3
        
        # Events should not be acknowledged when circuit breaker is triggered
        mock_outbox.acknowledge_event.assert_not_called()
    
    def test_recovery_with_exception_handling(self, mock_outbox, mock_client, recovery_config):
        """Test recovery handles exceptions gracefully."""
        task_id = "task_123"
        mock_outbox.get_all_pending_tasks.return_value = [task_id]
        
        # Mock exception during get_pending_events
        mock_outbox.get_pending_events.side_effect = Exception("Redis connection failed")
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=recovery_config
        )
        
        # Should not raise exception, but handle it gracefully
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 1
        assert stats.total_events_found == 0
        assert stats.failed_deliveries == 0  # No events to fail
    
    def test_shutdown_during_recovery(self, mock_outbox, mock_client):
        """Test graceful shutdown during recovery process."""
        # Create many tasks to ensure recovery takes time
        task_ids = [f"task_{i}" for i in range(100)]
        mock_outbox.get_all_pending_tasks.return_value = task_ids
        
        # Add a small delay to get_pending_events to simulate work
        def slow_get_pending_events(task_id):
            time.sleep(0.001)  # Small delay to allow shutdown to interrupt
            return []
        
        mock_outbox.get_pending_events.side_effect = slow_get_pending_events
        
        config = RecoveryConfig(
            enabled=True,
            startup_delay_seconds=0.0,
            batch_size=1,  # Process one at a time
        )
        
        service = EventRecoveryService(
            outbox=mock_outbox,
            client=mock_client,
            config=config
        )
        
        # Start background recovery
        service.start_recovery_service()
        
        # Give it a moment to start
        time.sleep(0.05)
        
        # Request shutdown
        stopped = service.stop_recovery_service(timeout_seconds=1.0)
        
        assert stopped is True
        # Recovery should have been interrupted (allow some tolerance)
        assert mock_outbox.get_pending_events.call_count <= 100


class TestRecoveryIntegration:
    """Integration tests with real Redis outbox."""
    
    def test_integration_with_real_outbox(self, mock_client):
        """Test recovery service with real Redis outbox (memory backend)."""
        # Use real outbox with memory backend
        outbox = RedisOutbox(backend="memory")
        
        # Store some test events
        task_id = "integration_task"
        events = []
        for i in range(3):
            event = {
                "eventId": f"evt_{uuid4().hex}",
                "eventVersion": 1,
                "taskId": task_id,
                "assistant": "ai-agent",
                "type": f"INTEGRATION_EVENT_{i}",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "seq": i,
                "payload": {"message": f"Integration event {i}"}
            }
            events.append(event)
            outbox.store_event(task_id, event)
        
        # Verify events are pending
        pending = outbox.get_pending_events(task_id)
        assert len(pending) == 3
        
        # Create recovery service
        config = RecoveryConfig(enabled=True, startup_delay_seconds=0.0)
        service = EventRecoveryService(
            outbox=outbox,
            client=mock_client,
            config=config
        )
        
        # Perform recovery
        stats = service.recover_events_now()
        
        assert stats.total_tasks_scanned == 1
        assert stats.total_events_found == 3
        assert stats.successful_deliveries == 3
        assert stats.failed_deliveries == 0
        
        # Verify events were acknowledged and removed from outbox
        remaining = outbox.get_pending_events(task_id)
        assert len(remaining) == 0
        
        # Verify client was called for each event
        assert mock_client.publish_event_with_retry_result.call_count == 3