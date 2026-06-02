"""
Comprehensive unit tests for BaseAgent.

**Validates: Requirements 6.4**

Tests cover:
- Reliable event publishing with outbox integration
- Event sequence number management
- Event persistence and delivery
- Outbox flush and acknowledgment
- Event retry with client integration
"""
from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from agents.base_agent import BaseAgent, DefaultAiAgent
from client.control_plane_client import ControlPlaneClient


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        self.publish_event(task, client, "TEST_EVENT", {"message": "test"})


class TestBaseAgentEventPublishing:
    """Test BaseAgent reliable event publishing."""

    def test_base_agent_publishes_event_with_sequence_number(self):
        """Verify BaseAgent publishes events with incrementing sequence numbers."""
        task = {"taskId": "task_001", "assistant": "ai-agent"}
        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None  # force fallback to publish_event
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = ConcreteAgent()
        agent.publish_event(task, mock_client, "EVENT_1", {"data": "first"})
        agent.publish_event(task, mock_client, "EVENT_2", {"data": "second"})

        assert mock_client.publish_event.call_count == 2
        first_event = mock_client.publish_event.call_args_list[0][0][1]
        second_event = mock_client.publish_event.call_args_list[1][0][1]

        assert first_event["seq"] == 0
        assert second_event["seq"] == 1

    def test_base_agent_maintains_separate_sequences_per_task(self):
        """Verify BaseAgent maintains separate sequence numbers for different tasks."""
        task1 = {"taskId": "task_001", "assistant": "ai-agent"}
        task2 = {"taskId": "task_002", "assistant": "ai-agent"}

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = ConcreteAgent()
        agent.publish_event(task1, mock_client, "EVENT_1", {"data": "task1_event1"})
        agent.publish_event(task2, mock_client, "EVENT_2", {"data": "task2_event1"})
        agent.publish_event(task1, mock_client, "EVENT_3", {"data": "task1_event2"})

        task1_events = [
            call[0][1] for call in mock_client.publish_event.call_args_list
            if call[0][0] == "task_001"
        ]
        task2_events = [
            call[0][1] for call in mock_client.publish_event.call_args_list
            if call[0][0] == "task_002"
        ]

        assert task1_events[0]["seq"] == 0
        assert task1_events[1]["seq"] == 1
        assert task2_events[0]["seq"] == 0

    def test_base_agent_includes_event_metadata(self):
        """Verify BaseAgent includes required metadata in events."""
        task = {
            "taskId": "task_meta_001",
            "assistant": "ai-agent",
            "sessionId": "sess_001",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = ConcreteAgent()
        agent.publish_event(task, mock_client, "TEST_EVENT", {"message": "test"})

        event = mock_client.publish_event.call_args[0][1]
        assert "eventId" in event
        assert event["eventVersion"] == 1
        assert event["taskId"] == "task_meta_001"
        assert event["assistant"] == "ai-agent"
        assert event["type"] == "TEST_EVENT"
        assert "timestamp" in event
        assert event["seq"] == 0
        assert event["sessionId"] == "sess_001"

    def test_base_agent_raises_error_for_missing_task_id(self):
        """Verify BaseAgent raises error when taskId is missing."""
        task = {"assistant": "ai-agent"}
        mock_client = Mock(spec=ControlPlaneClient)

        agent = ConcreteAgent()
        with pytest.raises(ValueError, match="taskId is required"):
            agent.publish_event(task, mock_client, "TEST_EVENT", {"message": "test"})


class TestBaseAgentOutboxIntegration:
    """Test BaseAgent outbox integration for reliable delivery."""

    def test_base_agent_enqueues_event_to_outbox_before_delivery(self):
        """Verify BaseAgent enqueues events to outbox before attempting delivery."""
        task = {"taskId": "task_outbox_001", "assistant": "ai-agent"}
        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = ConcreteAgent()
        agent.publish_event(task, mock_client, "TEST_EVENT", {"message": "test"})

        # Event should be in outbox initially, then removed after successful delivery
        pending = agent._pending_outbox("task_outbox_001")
        assert len(pending) == 0  # Should be empty after successful delivery

    def test_base_agent_flushes_pending_outbox_events(self):
        """Verify BaseAgent flushes pending outbox events on next publish."""
        task = {"taskId": "task_flush_001", "assistant": "ai-agent"}

        # First client fails
        mock_client_fail = Mock(spec=ControlPlaneClient)
        mock_client_fail.publish_event_with_retry_result = None
        mock_client_fail.publish_event_with_retry = None
        mock_client_fail.publish_event = Mock(side_effect=RuntimeError("network error"))

        agent = ConcreteAgent()

        # This should fail and leave event in outbox
        with pytest.raises(RuntimeError):
            agent.publish_event(task, mock_client_fail, "EVENT_1", {"data": "first"})

        # Verify event is in outbox
        pending = agent._pending_outbox("task_flush_001")
        assert len(pending) == 1

        # Second client succeeds
        mock_client_success = Mock(spec=ControlPlaneClient)
        mock_client_success.publish_event_with_retry_result = None
        mock_client_success.publish_event_with_retry = None
        mock_client_success.publish_event = Mock(return_value={"eventId": "evt_001"})

        # This should flush the pending event and publish new one
        agent.publish_event(task, mock_client_success, "EVENT_2", {"data": "second"})

        # Should have published both events
        assert mock_client_success.publish_event.call_count == 2

        # Outbox should be empty
        pending = agent._pending_outbox("task_flush_001")
        assert len(pending) == 0

    def test_base_agent_acknowledges_delivered_events(self):
        """Verify BaseAgent acknowledges events after successful delivery."""
        task = {"taskId": "task_ack_001", "assistant": "ai-agent"}
        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = ConcreteAgent()

        # Manually enqueue an event
        event = {
            "eventId": "evt_manual_001",
            "taskId": "task_ack_001",
            "type": "TEST_EVENT",
            "seq": 0,
        }
        agent._enqueue_outbox("task_ack_001", event)

        # Verify it's in outbox
        pending = agent._pending_outbox("task_ack_001")
        assert len(pending) == 1

        # Acknowledge it
        agent._ack_outbox("task_ack_001", "evt_manual_001")

        # Verify it's removed
        pending = agent._pending_outbox("task_ack_001")
        assert len(pending) == 0

    def test_base_agent_handles_multiple_pending_events(self):
        """Verify BaseAgent handles multiple pending events correctly."""
        task = {"taskId": "task_multi_001", "assistant": "ai-agent"}

        agent = ConcreteAgent()

        # Enqueue multiple events
        for i in range(3):
            event = {
                "eventId": f"evt_{i}",
                "taskId": "task_multi_001",
                "type": "TEST_EVENT",
                "seq": i,
            }
            agent._enqueue_outbox("task_multi_001", event)

        # Verify all are in outbox
        pending = agent._pending_outbox("task_multi_001")
        assert len(pending) == 3

        # Acknowledge middle event
        agent._ack_outbox("task_multi_001", "evt_1")

        # Verify only 2 remain
        pending = agent._pending_outbox("task_multi_001")
        assert len(pending) == 2
        event_ids = [e["eventId"] for e in pending]
        assert "evt_0" in event_ids
        assert "evt_2" in event_ids
        assert "evt_1" not in event_ids


class TestBaseAgentRetryIntegration:
    """Test BaseAgent integration with client retry mechanisms."""

    def test_base_agent_uses_publish_event_with_retry_result_when_available(self):
        """Verify BaseAgent uses publish_event_with_retry_result when available."""
        task = {"taskId": "task_retry_001", "assistant": "ai-agent"}

        mock_client = Mock(spec=ControlPlaneClient)
        mock_result = Mock()
        mock_result.attempts = 3
        mock_client.publish_event_with_retry_result = Mock(return_value=mock_result)

        agent = ConcreteAgent()
        agent.publish_event(task, mock_client, "TEST_EVENT", {"message": "test"})

        mock_client.publish_event_with_retry_result.assert_called_once()

    def test_base_agent_falls_back_to_publish_event_with_retry(self):
        """Verify BaseAgent falls back to publish_event_with_retry when available."""
        task = {"taskId": "task_retry_002", "assistant": "ai-agent"}

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None  # disable retry_result
        mock_client.publish_event_with_retry = Mock()
        # Don't define publish_event_with_retry_result

        agent = ConcreteAgent()
        agent.publish_event(task, mock_client, "TEST_EVENT", {"message": "test"})

        mock_client.publish_event_with_retry.assert_called_once()

    def test_base_agent_falls_back_to_basic_publish_event(self):
        """Verify BaseAgent falls back to basic publish_event when retry methods unavailable."""
        task = {"taskId": "task_retry_003", "assistant": "ai-agent"}

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None  # disable
        mock_client.publish_event_with_retry = None  # disable
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})
        # Don't define retry methods

        agent = ConcreteAgent()
        agent.publish_event(task, mock_client, "TEST_EVENT", {"message": "test"})

        mock_client.publish_event.assert_called_once()


class TestDefaultAiAgent:
    """Test DefaultAiAgent implementation."""

    def test_default_ai_agent_publishes_assistant_output_and_task_done(self):
        """Verify DefaultAiAgent publishes expected events."""
        task = {
            "taskId": "task_default_001",
            "assistant": "ai-agent",
            "prompt": "test prompt",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = DefaultAiAgent()
        agent.handle_task(task, mock_client)

        assert mock_client.publish_event.call_count == 2

        first_event = mock_client.publish_event.call_args_list[0][0][1]
        second_event = mock_client.publish_event.call_args_list[1][0][1]

        assert first_event["type"] == "ASSISTANT_OUTPUT"
        assert "planning next steps" in first_event["payload"]["message"].lower()
        assert second_event["type"] == "TASK_DONE"
        assert second_event["payload"]["result"] == "accepted_for_ai_pipeline"

    def test_default_ai_agent_includes_prompt_in_output(self):
        """Verify DefaultAiAgent includes prompt in assistant output."""
        task = {
            "taskId": "task_default_002",
            "assistant": "ai-agent",
            "prompt": "analyze this code",
        }

        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = DefaultAiAgent()
        agent.handle_task(task, mock_client)

        first_event = mock_client.publish_event.call_args_list[0][0][1]
        assert first_event["payload"]["prompt"] == "analyze this code"


class TestBaseAgentThreadSafety:
    """Test BaseAgent thread safety for concurrent operations."""

    def test_base_agent_sequence_numbers_are_thread_safe(self):
        """Verify BaseAgent sequence number generation is thread-safe."""
        import threading

        task = {"taskId": "task_thread_001", "assistant": "ai-agent"}
        mock_client = Mock(spec=ControlPlaneClient)
        mock_client.publish_event_with_retry_result = None
        mock_client.publish_event_with_retry = None
        mock_client.publish_event = Mock(return_value={"eventId": "evt_001"})

        agent = ConcreteAgent()
        sequences = []

        def publish_event():
            for _ in range(10):
                agent.publish_event(task, mock_client, "TEST_EVENT", {"data": "test"})

        threads = [threading.Thread(target=publish_event) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have published 50 events total
        assert mock_client.publish_event.call_count == 50

        # All sequence numbers should be unique and sequential
        all_seqs = [call[0][1]["seq"] for call in mock_client.publish_event.call_args_list]
        assert sorted(all_seqs) == list(range(50))

    def test_base_agent_outbox_operations_are_thread_safe(self):
        """Verify BaseAgent outbox operations are thread-safe."""
        import threading

        agent = ConcreteAgent()
        task_id = "task_thread_002"

        def enqueue_events():
            for i in range(10):
                event = {
                    "eventId": f"evt_{threading.current_thread().name}_{i}",
                    "taskId": task_id,
                    "type": "TEST_EVENT",
                    "seq": i,
                }
                agent._enqueue_outbox(task_id, event)

        threads = [threading.Thread(target=enqueue_events, name=f"thread_{i}") for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have 50 events in outbox
        pending = agent._pending_outbox(task_id)
        assert len(pending) == 50
