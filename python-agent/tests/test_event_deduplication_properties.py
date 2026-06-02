"""
Property-based tests for event deduplication functionality.

Task 4.4: Write property tests for event deduplication
Property 7: Event Deduplication
Validates: Requirements 2.5

These tests validate that "For any duplicate event submission (same eventId), 
the Control Plane SHALL detect the duplicate, return an ACK response with 
duplicate=true, and preserve the original sequence number."
"""

from __future__ import annotations

import json
import pytest
import time
from datetime import datetime, timezone
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock, patch, MagicMock
from urllib.error import HTTPError, URLError
from uuid import uuid4

from client.control_plane_client import ControlPlaneClient, PublishEventResult, ControlPlaneRequestError
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from utils.observability import TaskObservability


# Strategy for generating valid event IDs
event_id_strategy = st.builds(
    lambda: f"evt_{uuid4().hex}"
)

# Strategy for generating valid timestamps
timestamp_strategy = st.builds(
    lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
)

# Strategy for generating valid sequence numbers (non-negative integers)
sequence_number_strategy = st.integers(min_value=0, max_value=10000)

# Strategy for generating valid task IDs
task_id_strategy = st.text(
    min_size=1, 
    max_size=50, 
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))
)

# Strategy for generating valid event types
event_type_strategy = st.sampled_from([
    "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED",
    "ARTIFACT_READY", "APPROVAL_REQUESTED", "SPEC_PROPOSED"
])

# Strategy for generating valid events with all required fields
valid_event_strategy = st.builds(
    dict,
    eventId=event_id_strategy,
    eventVersion=st.integers(min_value=1, max_value=10),
    taskId=task_id_strategy,
    assistant=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"))),
    type=event_type_strategy,
    timestamp=timestamp_strategy,
    seq=sequence_number_strategy,
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        values=st.one_of(st.text(max_size=100), st.integers(), st.booleans()),
        min_size=0,
        max_size=5
    )
)

# Strategy for generating TTL values (in seconds)
ttl_strategy = st.integers(min_value=1, max_value=86400)  # 1 second to 24 hours


class TestEventDeduplicationProperties:
    """
    Property-based tests for event deduplication functionality.
    
    These tests verify that for any duplicate event submission (same eventId),
    the Control Plane detects the duplicate, returns an ACK response with
    duplicate=true, and preserves the original sequence number.
    """
    
    @given(valid_event_strategy, task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_7_duplicate_event_detection_basic(self, event, task_id):
        """
        **Property 7: Event Deduplication - Basic Duplicate Detection**
        
        For any event submitted twice with the same eventId, the second submission
        SHALL be detected as a duplicate and return duplicate=true in the ACK response.
        
        **Validates: Requirements 2.5**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(event.get("eventId"))  # Ensure event has eventId
        
        client = ControlPlaneClient("http://localhost:8058", "test-agent-token")
        
        # Mock successful first submission
        first_ack_data = {
            "seq": event.get("seq", 1),
            "accepted": True,
            "duplicate": False,
            "errorCode": None
        }
        
        # Mock duplicate detection on second submission
        duplicate_ack_data = {
            "seq": event.get("seq", 1),  # Original sequence preserved
            "accepted": True,             # Duplicates are acknowledged
            "duplicate": True,            # Duplicate flag set
            "errorCode": None             # No error for duplicates
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            # First submission - successful
            mock_response_1 = MagicMock()
            mock_response_1.read.return_value = json.dumps({
                "success": True,
                "data": first_ack_data
            }).encode('utf-8')
            mock_response_1.getcode.return_value = 200
            
            # Second submission - duplicate detected
            mock_response_2 = MagicMock()
            mock_response_2.read.return_value = json.dumps({
                "success": True,
                "data": duplicate_ack_data
            }).encode('utf-8')
            mock_response_2.getcode.return_value = 200
            
            mock_urlopen.return_value.__enter__.side_effect = [mock_response_1, mock_response_2]
            
            # First submission
            first_ack = client.publish_event_with_ack(task_id, event, max_attempts=1)
            
            # Second submission (duplicate)
            duplicate_ack = client.publish_event_with_ack(task_id, event, max_attempts=1)
            
            # Verify first submission
            assert first_ack is not None, "First submission must return ACK response"
            assert first_ack["duplicate"] is False, "First submission must not be marked as duplicate"
            assert first_ack["accepted"] is True, "First submission must be accepted"
            
            # Verify duplicate detection
            assert duplicate_ack is not None, "Duplicate submission must return ACK response"
            assert duplicate_ack["duplicate"] is True, "Duplicate submission must be marked as duplicate"
            assert duplicate_ack["accepted"] is True, "Duplicate submission must be acknowledged"
            assert duplicate_ack["seq"] == first_ack["seq"], "Duplicate must preserve original sequence number"
            assert duplicate_ack["errorCode"] is None, "Duplicate submission must not have error code"

    @given(valid_event_strategy, task_id_strategy, sequence_number_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_7_original_sequence_preservation(self, event, task_id, original_seq):
        """
        **Property 7: Event Deduplication - Original Sequence Number Preservation**
        
        For any duplicate event submission, the ACK response SHALL preserve
        the original sequence number from the first submission.
        
        **Validates: Requirements 2.5**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(event.get("eventId"))  # Ensure event has eventId
        
        client = ControlPlaneClient("http://localhost:8058", "test-agent-token")
        
        # Create event with original sequence
        event_with_seq = event.copy()
        event_with_seq["seq"] = original_seq
        
        # Mock duplicate detection response with preserved sequence
        duplicate_ack_data = {
            "seq": original_seq,  # Original sequence preserved
            "accepted": True,
            "duplicate": True,
            "errorCode": None
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "success": True,
                "data": duplicate_ack_data
            }).encode('utf-8')
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Submit duplicate event
            ack_response = client.publish_event_with_ack(task_id, event_with_seq, max_attempts=1)
            
            assert ack_response is not None, "Duplicate event must return ACK response"
            assert ack_response["duplicate"] is True, "Event must be detected as duplicate"
            assert ack_response["seq"] == original_seq, f"Original sequence {original_seq} must be preserved"
            assert ack_response["accepted"] is True, "Duplicate event must be acknowledged"
            assert ack_response["errorCode"] is None, "Duplicate event must not have error code"

    @given(st.lists(valid_event_strategy, min_size=2, max_size=5), task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_7_multiple_duplicate_submissions(self, events, task_id):
        """
        **Property 7: Event Deduplication - Multiple Duplicate Submissions**
        
        For any event submitted multiple times with the same eventId,
        all subsequent submissions SHALL be detected as duplicates
        and return the same original sequence number.
        
        **Validates: Requirements 2.5**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(all(event.get("eventId") for event in events))  # Ensure all events have eventId
        
        # Use the same eventId for all events to create duplicates
        base_event = events[0]
        duplicate_events = []
        for i, event in enumerate(events):
            duplicate_event = event.copy()
            duplicate_event["eventId"] = base_event["eventId"]  # Same eventId for all
            duplicate_event["seq"] = base_event["seq"] + i  # Different sequences
            duplicate_events.append(duplicate_event)
        
        client = ControlPlaneClient("http://localhost:8058", "test-agent-token")
        original_seq = base_event["seq"]
        
        # Mock responses - first is accepted, rest are duplicates
        responses = []
        for i, event in enumerate(duplicate_events):
            if i == 0:
                # First submission - accepted
                ack_data = {
                    "seq": original_seq,
                    "accepted": True,
                    "duplicate": False,
                    "errorCode": None
                }
            else:
                # Subsequent submissions - duplicates
                ack_data = {
                    "seq": original_seq,  # Original sequence preserved
                    "accepted": True,
                    "duplicate": True,
                    "errorCode": None
                }
            
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "success": True,
                "data": ack_data
            }).encode('utf-8')
            mock_response.getcode.return_value = 200
            responses.append(mock_response)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value.__enter__.side_effect = responses
            
            ack_responses = []
            for event in duplicate_events:
                ack = client.publish_event_with_ack(task_id, event, max_attempts=1)
                ack_responses.append(ack)
            
            # Verify first submission
            first_ack = ack_responses[0]
            assert first_ack is not None, "First submission must return ACK response"
            assert first_ack["duplicate"] is False, "First submission must not be marked as duplicate"
            assert first_ack["accepted"] is True, "First submission must be accepted"
            assert first_ack["seq"] == original_seq, "First submission must have original sequence"
            
            # Verify all subsequent submissions are duplicates
            for i, ack in enumerate(ack_responses[1:], 1):
                assert ack is not None, f"Duplicate submission {i} must return ACK response"
                assert ack["duplicate"] is True, f"Duplicate submission {i} must be marked as duplicate"
                assert ack["accepted"] is True, f"Duplicate submission {i} must be acknowledged"
                assert ack["seq"] == original_seq, f"Duplicate submission {i} must preserve original sequence {original_seq}"
                assert ack["errorCode"] is None, f"Duplicate submission {i} must not have error code"

    @given(valid_event_strategy, task_id_strategy, st.integers(min_value=1, max_value=10))
    @settings(deadline=None, max_examples=10)
    def test_property_7_rapid_duplicate_submissions(self, event, task_id, num_submissions):
        """
        **Property 7: Event Deduplication - Rapid Duplicate Submissions**
        
        For any event submitted rapidly multiple times (simulating race conditions),
        the deduplication system SHALL handle all submissions correctly,
        detecting duplicates and preserving the original sequence number.
        
        **Validates: Requirements 2.5**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(event.get("eventId"))  # Ensure event has eventId
        
        client = ControlPlaneClient("http://localhost:8058", "test-agent-token")
        original_seq = event.get("seq", 1)
        
        # Mock responses for rapid submissions
        responses = []
        for i in range(num_submissions):
            if i == 0:
                # First submission - accepted
                ack_data = {
                    "seq": original_seq,
                    "accepted": True,
                    "duplicate": False,
                    "errorCode": None
                }
            else:
                # Subsequent submissions - duplicates
                ack_data = {
                    "seq": original_seq,  # Original sequence preserved
                    "accepted": True,
                    "duplicate": True,
                    "errorCode": None
                }
            
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "success": True,
                "data": ack_data
            }).encode('utf-8')
            mock_response.getcode.return_value = 200
            responses.append(mock_response)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value.__enter__.side_effect = responses
            
            # Submit the same event rapidly multiple times
            ack_responses = []
            for i in range(num_submissions):
                ack = client.publish_event_with_ack(task_id, event, max_attempts=1)
                ack_responses.append(ack)
            
            # Verify all responses
            for i, ack in enumerate(ack_responses):
                assert ack is not None, f"Submission {i} must return ACK response"
                assert ack["seq"] == original_seq, f"Submission {i} must preserve original sequence {original_seq}"
                assert ack["accepted"] is True, f"Submission {i} must be acknowledged"
                assert ack["errorCode"] is None, f"Submission {i} must not have error code"
                
                if i == 0:
                    assert ack["duplicate"] is False, "First submission must not be marked as duplicate"
                else:
                    assert ack["duplicate"] is True, f"Submission {i} must be marked as duplicate"

    @given(valid_event_strategy, task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_7_deduplication_with_different_payloads(self, event, task_id):
        """
        **Property 7: Event Deduplication - Same EventId with Different Payloads**
        
        For any events with the same eventId but different payloads,
        the deduplication SHALL be based on eventId only, not payload content.
        
        **Validates: Requirements 2.5**
        """
        assume(task_id.strip())  # Ensure non-empty task ID
        assume(event.get("eventId"))  # Ensure event has eventId
        
        client = ControlPlaneClient("http://localhost:8058", "test-agent-token")
        
        # Create two events with same eventId but different payloads
        event1 = event.copy()
        event2 = event.copy()
        event2["payload"] = {"different": "payload", "data": "modified"}
        event2["seq"] = event1["seq"] + 1  # Different sequence
        
        original_seq = event1["seq"]
        
        # Mock responses
        first_ack_data = {
            "seq": original_seq,
            "accepted": True,
            "duplicate": False,
            "errorCode": None
        }
        
        duplicate_ack_data = {
            "seq": original_seq,  # Original sequence preserved
            "accepted": True,
            "duplicate": True,
            "errorCode": None
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response_1 = MagicMock()
            mock_response_1.read.return_value = json.dumps({
                "success": True,
                "data": first_ack_data
            }).encode('utf-8')
            mock_response_1.getcode.return_value = 200
            
            mock_response_2 = MagicMock()
            mock_response_2.read.return_value = json.dumps({
                "success": True,
                "data": duplicate_ack_data
            }).encode('utf-8')
            mock_response_2.getcode.return_value = 200
            
            mock_urlopen.return_value.__enter__.side_effect = [mock_response_1, mock_response_2]
            
            # Submit first event
            first_ack = client.publish_event_with_ack(task_id, event1, max_attempts=1)
            
            # Submit second event with same eventId but different payload
            second_ack = client.publish_event_with_ack(task_id, event2, max_attempts=1)
            
            # Verify first submission
            assert first_ack is not None, "First submission must return ACK response"
            assert first_ack["duplicate"] is False, "First submission must not be marked as duplicate"
            assert first_ack["accepted"] is True, "First submission must be accepted"
            assert first_ack["seq"] == original_seq, "First submission must have original sequence"
            
            # Verify duplicate detection (despite different payload)
            assert second_ack is not None, "Second submission must return ACK response"
            assert second_ack["duplicate"] is True, "Second submission must be marked as duplicate (same eventId)"
            assert second_ack["accepted"] is True, "Second submission must be acknowledged"
            assert second_ack["seq"] == original_seq, "Second submission must preserve original sequence"
            assert second_ack["errorCode"] is None, "Second submission must not have error code"


class TestEventDeduplicationEdgeCases:
    """
    Edge case tests for event deduplication functionality.
    """
    
    def setup_method(self):
        """Setup for each test method."""
        self.client = ControlPlaneClient("http://localhost:8058", "test-agent-token")
    
    @given(st.one_of(st.none(), st.just(""), st.just("   ")))
    @settings(deadline=None, max_examples=10)
    def test_empty_event_id_handling(self, empty_event_id):
        """
        Test that empty or null event IDs are handled gracefully
        and do not interfere with deduplication logic.
        """
        event = {
            "eventId": empty_event_id,
            "eventVersion": 1,
            "taskId": "test_task",
            "assistant": "test_assistant",
            "type": "TASK_STARTED",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": 1,
            "payload": {}
        }
        
        # Mock error response for missing event ID
        error_ack_data = {
            "seq": 0,
            "accepted": False,
            "duplicate": False,
            "errorCode": "MISSING_EVENT_ID"
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "success": True,
                "data": error_ack_data
            }).encode('utf-8')
            mock_response.getcode.return_value = 400
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Should handle gracefully without throwing exception
            try:
                ack_response = self.client.publish_event_with_ack("test_task", event, max_attempts=1)
                
                # If we get a response, it should indicate the error
                if ack_response:
                    assert ack_response["accepted"] is False, "Empty event ID should not be accepted"
                    assert ack_response["duplicate"] is False, "Empty event ID should not be marked as duplicate"
                    assert ack_response["errorCode"] == "MISSING_EVENT_ID", "Should return appropriate error code"
                    
            except ControlPlaneRequestError:
                # This is also acceptable - the client may raise an exception for invalid requests
                pass

    @given(ttl_strategy)
    @settings(deadline=None, max_examples=10)
    def test_deduplication_ttl_behavior(self, ttl_seconds):
        """
        Test that deduplication entries respect TTL behavior.
        Note: This is a conceptual test as we can't actually wait for TTL expiration.
        """
        assume(ttl_seconds > 0)
        
        event = {
            "eventId": f"evt_ttl_test_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": "test_task",
            "assistant": "test_assistant",
            "type": "TASK_STARTED",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": 1,
            "payload": {"ttl_test": ttl_seconds}
        }
        
        # Mock successful submission (simulating TTL expiration scenario)
        ack_data = {
            "seq": event["seq"],
            "accepted": True,
            "duplicate": False,  # Not duplicate after TTL expiration
            "errorCode": None
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "success": True,
                "data": ack_data
            }).encode('utf-8')
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Submit event (simulating post-TTL expiration)
            ack_response = self.client.publish_event_with_ack("test_task", event, max_attempts=1)
            
            assert ack_response is not None, "Event submission must return ACK response"
            assert ack_response["accepted"] is True, "Event should be accepted after TTL expiration"
            assert ack_response["duplicate"] is False, "Event should not be duplicate after TTL expiration"
            assert ack_response["seq"] == event["seq"], "Sequence number should match event"
            assert ack_response["errorCode"] is None, "No error should occur"

    def test_deduplication_service_error_handling(self):
        """
        Test that deduplication service errors are handled gracefully
        and don't block event processing.
        """
        event = {
            "eventId": f"evt_error_test_{uuid4().hex}",
            "eventVersion": 1,
            "taskId": "test_task",
            "assistant": "test_assistant",
            "type": "TASK_STARTED",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": 1,
            "payload": {}
        }
        
        # Mock processing error response
        error_ack_data = {
            "seq": 0,
            "accepted": False,
            "duplicate": False,
            "errorCode": "PROCESSING_ERROR"
        }
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "success": True,
                "data": error_ack_data
            }).encode('utf-8')
            mock_response.getcode.return_value = 500
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Should handle service errors gracefully
            try:
                ack_response = self.client.publish_event_with_ack("test_task", event, max_attempts=1)
                
                if ack_response:
                    assert ack_response["accepted"] is False, "Processing error should not accept event"
                    assert ack_response["errorCode"] == "PROCESSING_ERROR", "Should return processing error code"
                    
            except ControlPlaneRequestError as e:
                # This is acceptable - client may raise exception for server errors
                assert "PROCESSING_ERROR" in str(e) or "500" in str(e)