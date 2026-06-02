"""
Property-based tests for event ACK protocol compliance.

Task 4.3: Write property tests for event ACK protocol
Property 6: Event ACK Protocol Compliance
Validates: Requirements 2.4

These tests validate that "For any event submission, the Control Plane SHALL return 
an explicit ACK response containing the sequence number, acceptance status, duplicate 
detection, and error code (if applicable)."
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

# Strategy for generating valid events with all required ACK protocol fields
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

# Strategy for generating valid ACK responses
valid_ack_response_strategy = st.builds(
    dict,
    seq=sequence_number_strategy,
    accepted=st.booleans(),
    duplicate=st.booleans(),
    errorCode=st.one_of(
        st.none(),
        st.sampled_from([
            "INVALID_NODE_ID", "NODE_NOT_REGISTERED", "MISSING_EVENT_ID",
            "TASK_NOT_FOUND", "PROCESSING_ERROR", "UNKNOWN_ERROR"
        ])
    )
)

# Strategy for generating Control Plane response format
control_plane_response_strategy = st.builds(
    dict,
    success=st.booleans(),
    data=valid_ack_response_strategy
)

# Strategy for generating HTTP status codes
http_status_strategy = st.sampled_from([200, 400, 403, 404, 500, 502, 503])


class TestEventAckProtocolProperties:
    """
    Property-based tests for event ACK protocol compliance.
    
    **Task 4.3: Write property tests for event ACK protocol**
    **Property 6: Event ACK Protocol Compliance**
    **Validates: Requirements 2.4**
    
    These tests verify that for any event submission, the Control Plane returns
    an explicit ACK response containing sequence number, acceptance status,
    duplicate detection, and error code (if applicable).
    """
    
    @given(valid_event_strategy, task_id_strategy, valid_ack_response_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_6_event_ack_protocol_compliance_structure(self, event, task_id, ack_data):
        """
        **Property 6: Event ACK Protocol Compliance - Response Structure**
        
        For any event submission, the Control Plane SHALL return an explicit ACK 
        response containing the sequence number, acceptance status, duplicate 
        detection, and error code (if applicable).
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Mock Control Plane response with valid ACK structure
        control_plane_response = {
            "success": True,
            "data": ack_data
        }
        
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Publish event and extract ACK response
            response = client.publish_event(task_id, event)
            ack_response = client.extract_ack_response(response)
            
            # Verify ACK response structure compliance
            assert ack_response is not None, "ACK response must not be None"
            assert "seq" in ack_response, "ACK response must contain sequence number"
            assert "accepted" in ack_response, "ACK response must contain acceptance status"
            assert "duplicate" in ack_response, "ACK response must contain duplicate detection"
            assert "errorCode" in ack_response, "ACK response must contain error code field"
            
            # Verify field types
            assert isinstance(ack_response["seq"], int), "Sequence number must be integer"
            assert isinstance(ack_response["accepted"], bool), "Acceptance status must be boolean"
            assert isinstance(ack_response["duplicate"], bool), "Duplicate detection must be boolean"
            assert (ack_response["errorCode"] is None or 
                   isinstance(ack_response["errorCode"], str)), "Error code must be string or None"
            
            # Verify sequence number constraints
            assert ack_response["seq"] >= 0, "Sequence number must be non-negative"
            
            # Verify ACK response validation passes
            assert client.validate_ack_response(ack_response), "ACK response must pass validation"

    @given(valid_event_strategy, task_id_strategy, sequence_number_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_6_sequence_number_preservation(self, event, task_id, seq_number):
        """
        **Property 6: Event ACK Protocol Compliance - Sequence Number Preservation**
        
        For any event submission, the ACK response SHALL preserve the original 
        sequence number from the event.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        # Set the sequence number in the event
        event["seq"] = seq_number
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Mock successful ACK response with preserved sequence number
        ack_data = {
            "seq": seq_number,
            "accepted": True,
            "duplicate": False,
            "errorCode": None
        }
        
        control_plane_response = {
            "success": True,
            "data": ack_data
        }
        
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Publish event and verify sequence number preservation
            ack_response = client.publish_event_with_ack(task_id, event, max_attempts=1)
            
            assert ack_response is not None, "ACK response must not be None"
            assert ack_response["seq"] == seq_number, f"ACK sequence number {ack_response['seq']} must match event sequence number {seq_number}"
            
            # Verify validation with expected sequence number
            assert client.validate_ack_response(ack_response, expected_seq=seq_number), "ACK response must validate with expected sequence number"

    @given(valid_event_strategy, task_id_strategy)
    @settings(deadline=None, max_examples=10)
    def test_property_6_acceptance_status_accuracy(self, event, task_id):
        """
        **Property 6: Event ACK Protocol Compliance - Acceptance Status Accuracy**
        
        For any event submission, the ACK response SHALL accurately reflect whether 
        the event was accepted or rejected by the Control Plane.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Test both accepted and rejected scenarios
        test_scenarios = [
            # Accepted event
            {
                "ack_data": {"seq": event.get("seq", 1), "accepted": True, "duplicate": False, "errorCode": None},
                "http_status": 200,
                "should_raise": False
            },
            # Rejected event - non-retryable error
            {
                "ack_data": {"seq": 0, "accepted": False, "duplicate": False, "errorCode": "TASK_NOT_FOUND"},
                "http_status": 404,
                "should_raise": True
            },
            # Rejected event - retryable error
            {
                "ack_data": {"seq": 0, "accepted": False, "duplicate": False, "errorCode": "PROCESSING_ERROR"},
                "http_status": 500,
                "should_raise": True
            }
        ]
        
        for scenario in test_scenarios:
            with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
                control_plane_response = {
                    "success": True,
                    "data": scenario["ack_data"]
                }
                
                mock_response = Mock()
                mock_response.getcode.return_value = scenario["http_status"]
                mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                if scenario["should_raise"]:
                    # Rejected events should raise exceptions
                    with pytest.raises(ControlPlaneRequestError):
                        client.publish_event_with_ack(task_id, event, max_attempts=1)
                else:
                    # Accepted events should return ACK response
                    ack_response = client.publish_event_with_ack(task_id, event, max_attempts=1)
                    assert ack_response is not None, "Accepted event must return ACK response"
                    assert ack_response["accepted"] is True, "Accepted event ACK must have accepted=True"

    @given(valid_event_strategy, task_id_strategy, sequence_number_strategy)
    def test_property_6_duplicate_detection_in_ack(self, event, task_id, original_seq):
        """
        **Property 6: Event ACK Protocol Compliance - Duplicate Detection**
        
        For any duplicate event submission, the ACK response SHALL indicate 
        duplicate detection and return the original sequence number.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Mock duplicate event ACK response
        ack_data = {
            "seq": original_seq,  # Original sequence number preserved
            "accepted": True,     # Duplicates are "accepted" (acknowledged)
            "duplicate": True,    # Duplicate flag set
            "errorCode": None     # No error for duplicates
        }
        
        control_plane_response = {
            "success": True,
            "data": ack_data
        }
        
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Publish duplicate event
            ack_response = client.publish_event_with_ack(task_id, event, max_attempts=1)
            
            assert ack_response is not None, "Duplicate event must return ACK response"
            assert ack_response["duplicate"] is True, "Duplicate event ACK must have duplicate=True"
            assert ack_response["accepted"] is True, "Duplicate event ACK must have accepted=True"
            assert ack_response["seq"] == original_seq, "Duplicate event ACK must preserve original sequence number"
            assert ack_response["errorCode"] is None, "Duplicate event ACK must not have error code"

    @given(valid_event_strategy, task_id_strategy)
    def test_property_6_error_code_handling(self, event, task_id):
        """
        **Property 6: Event ACK Protocol Compliance - Error Code Handling**
        
        For any event submission that results in an error, the ACK response 
        SHALL contain an appropriate error code.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Test various error scenarios
        error_scenarios = [
            {"errorCode": "INVALID_NODE_ID", "accepted": False, "retryable": False},
            {"errorCode": "NODE_NOT_REGISTERED", "accepted": False, "retryable": False},
            {"errorCode": "MISSING_EVENT_ID", "accepted": False, "retryable": False},
            {"errorCode": "TASK_NOT_FOUND", "accepted": False, "retryable": False},
            {"errorCode": "PROCESSING_ERROR", "accepted": False, "retryable": True},
        ]
        
        for scenario in error_scenarios:
            with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
                ack_data = {
                    "seq": 0,
                    "accepted": scenario["accepted"],
                    "duplicate": False,
                    "errorCode": scenario["errorCode"]
                }
                
                control_plane_response = {
                    "success": True,
                    "data": ack_data
                }
                
                mock_response = Mock()
                mock_response.getcode.return_value = 500 if scenario["retryable"] else 400
                mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                # Error events should raise exceptions
                with pytest.raises(ControlPlaneRequestError) as exc_info:
                    client.publish_event_with_ack(task_id, event, max_attempts=1)
                
                # Verify error code is included in exception message
                assert scenario["errorCode"] in str(exc_info.value), f"Exception must contain error code {scenario['errorCode']}"
                
                # Verify retryable classification
                assert exc_info.value.retryable == scenario["retryable"], f"Error {scenario['errorCode']} retryable classification incorrect"

    @given(valid_event_strategy, task_id_strategy)
    def test_property_6_ack_response_validation_edge_cases(self, event, task_id):
        """
        **Property 6: Event ACK Protocol Compliance - Validation Edge Cases**
        
        For any event submission, the client SHALL properly validate ACK response 
        structure and reject invalid responses.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        # Test invalid ACK response formats
        invalid_responses = [
            # Missing data field
            {"success": True},
            # Invalid data type
            {"success": True, "data": "invalid"},
            # Missing required fields
            {"success": True, "data": {"seq": 123}},
            {"success": True, "data": {"seq": 123, "accepted": True}},
            {"success": True, "data": {"seq": 123, "accepted": True, "duplicate": False}},
            # Invalid field types
            {"success": True, "data": {"seq": "123", "accepted": True, "duplicate": False, "errorCode": None}},
            {"success": True, "data": {"seq": 123, "accepted": "true", "duplicate": False, "errorCode": None}},
            {"success": True, "data": {"seq": 123, "accepted": True, "duplicate": "false", "errorCode": None}},
            {"success": True, "data": {"seq": 123, "accepted": True, "duplicate": False, "errorCode": 123}},
            # Invalid sequence number (negative)
            {"success": True, "data": {"seq": -1, "accepted": True, "duplicate": False, "errorCode": None}},
        ]
        
        for invalid_response in invalid_responses:
            # Create a fresh client to avoid circuit breaker state interference
            client = ControlPlaneClient(
                base_url="http://localhost:8058",
                agent_token="test-token",
                timeout_seconds=5
            )
            
            with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
                mock_response = Mock()
                mock_response.getcode.return_value = 200
                mock_response.read.return_value = json.dumps(invalid_response).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                # Invalid ACK responses should raise exceptions
                with pytest.raises(ControlPlaneRequestError) as exc_info:
                    client.publish_event_with_ack(task_id, event, max_attempts=1)
                
                assert "Invalid ACK response format" in str(exc_info.value), "Invalid ACK format must be detected"
                assert exc_info.value.retryable is True, "Invalid ACK format should be retryable"

    @given(valid_event_strategy, task_id_strategy, http_status_strategy)
    def test_property_6_ack_protocol_with_http_errors(self, event, task_id, status_code):
        """
        **Property 6: Event ACK Protocol Compliance - HTTP Error Handling**
        
        For any event submission that results in HTTP errors, the client SHALL 
        handle the error appropriately while maintaining ACK protocol compliance.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            # Mock HTTP error
            error_response = HTTPError(
                url="http://localhost:8058/api/v1/events/ingest",
                code=status_code,
                msg="HTTP Error",
                hdrs={},
                fp=Mock()
            )
            error_response.read.return_value = b"HTTP Error Response"
            mock_urlopen.side_effect = error_response
            
            # HTTP errors should raise ControlPlaneRequestError
            with pytest.raises(ControlPlaneRequestError) as exc_info:
                client.publish_event_with_ack(task_id, event, max_attempts=1)
            
            # Verify error contains status code information
            assert str(status_code) in str(exc_info.value), f"Exception must contain HTTP status code {status_code}"
            
            # Verify retryable classification based on HTTP status
            expected_retryable = status_code >= 500 or status_code in {408, 425, 429}
            assert exc_info.value.retryable == expected_retryable, f"HTTP {status_code} retryable classification incorrect"

    @given(valid_event_strategy, task_id_strategy)
    @settings(max_examples=50, deadline=10000)  # Reduced examples for performance
    def test_property_6_ack_protocol_with_retry_result(self, event, task_id):
        """
        **Property 6: Event ACK Protocol Compliance - Retry Result Integration**
        
        For any event submission using retry mechanism, the PublishEventResult 
        SHALL include the ACK response data.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Mock successful ACK response
        ack_data = {
            "seq": event.get("seq", 1),
            "accepted": True,
            "duplicate": False,
            "errorCode": None
        }
        
        control_plane_response = {
            "success": True,
            "data": ack_data
        }
        
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            # Test retry result includes ACK response
            result = client.publish_event_with_retry_result(task_id, event, max_attempts=1)
            
            assert result is not None, "Retry result must not be None"
            assert isinstance(result, PublishEventResult), "Result must be PublishEventResult instance"
            assert result.response is not None, "Result must include response"
            assert result.ack_response is not None, "Result must include ACK response"
            assert result.final_error is None, "Successful result must not have error"
            assert result.attempts == 1, "Single attempt should be recorded"
            
            # Verify ACK response structure in result
            ack_response = result.ack_response
            assert ack_response["seq"] == ack_data["seq"], "ACK sequence number must match"
            assert ack_response["accepted"] == ack_data["accepted"], "ACK acceptance status must match"
            assert ack_response["duplicate"] == ack_data["duplicate"], "ACK duplicate status must match"
            assert ack_response["errorCode"] == ack_data["errorCode"], "ACK error code must match"

    @given(valid_event_strategy, task_id_strategy)
    def test_property_6_ack_protocol_boundary_conditions(self, event, task_id):
        """
        **Property 6: Event ACK Protocol Compliance - Boundary Conditions**
        
        For any event submission with boundary condition values, the ACK protocol 
        SHALL handle them correctly.
        
        **Validates: Requirements 2.4**
        """
        assume(task_id.strip())
        assume(event.get("eventId") and event.get("eventId").strip())
        
        client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        # Test boundary conditions
        boundary_scenarios = [
            # Minimum sequence number
            {"seq": 0, "accepted": True, "duplicate": False, "errorCode": None},
            # Maximum reasonable sequence number
            {"seq": 999999, "accepted": True, "duplicate": False, "errorCode": None},
            # Empty error code (None)
            {"seq": 1, "accepted": False, "duplicate": False, "errorCode": None},
            # Long error code
            {"seq": 1, "accepted": False, "duplicate": False, "errorCode": "VERY_LONG_ERROR_CODE_NAME"},
        ]
        
        for ack_data in boundary_scenarios:
            with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
                control_plane_response = {
                    "success": True,
                    "data": ack_data
                }
                
                mock_response = Mock()
                mock_response.getcode.return_value = 200 if ack_data["accepted"] else 400
                mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                if ack_data["accepted"]:
                    # Accepted events should return ACK response
                    ack_response = client.publish_event_with_ack(task_id, event, max_attempts=1)
                    assert ack_response is not None, "Boundary condition ACK must not be None"
                    assert client.validate_ack_response(ack_response), "Boundary condition ACK must be valid"
                    assert ack_response["seq"] == ack_data["seq"], "Boundary sequence number must be preserved"
                else:
                    # Rejected events should raise exceptions
                    with pytest.raises(ControlPlaneRequestError):
                        client.publish_event_with_ack(task_id, event, max_attempts=1)


class TestEventAckProtocolEdgeCases:
    """
    Additional property-based tests for ACK protocol edge cases and error conditions.
    """
    
    def setup_method(self):
        """Set up test client."""
        self.client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )

    @given(st.text(max_size=0))  # Empty task ID
    def test_empty_task_id_handling(self, empty_task_id):
        """Test ACK protocol with empty task ID."""
        event = {"eventId": "evt-123", "type": "TASK_STARTED", "seq": 1}
        
        # Empty task IDs should be handled gracefully
        # The URL encoding will handle this, but the server may reject it
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 400
            mock_response.read.return_value = b'{"success": false, "error": "Invalid task ID"}'
            mock_urlopen.side_effect = HTTPError(
                url="http://localhost:8058/api/v1/events/ingest",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=Mock()
            )
            mock_urlopen.side_effect.read.return_value = b'Bad Request'
            
            with pytest.raises(ControlPlaneRequestError):
                self.client.publish_event_with_ack(empty_task_id, event, max_attempts=1)

    @given(st.dictionaries(st.text(), st.text(), max_size=0))  # Empty event
    def test_empty_event_handling(self, empty_event):
        """Test ACK protocol with empty event."""
        task_id = "task-123"
        
        # Empty events should be handled gracefully
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            ack_data = {
                "seq": 0,
                "accepted": False,
                "duplicate": False,
                "errorCode": "MISSING_EVENT_ID"
            }
            
            control_plane_response = {
                "success": True,
                "data": ack_data
            }
            
            mock_response = Mock()
            mock_response.getcode.return_value = 400
            mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            with pytest.raises(ControlPlaneRequestError) as exc_info:
                self.client.publish_event_with_ack(task_id, empty_event, max_attempts=1)
            
            assert "MISSING_EVENT_ID" in str(exc_info.value)

    @given(st.integers(min_value=-1000, max_value=-1))  # Negative sequence numbers
    def test_negative_sequence_number_validation(self, negative_seq):
        """Test ACK response validation with negative sequence numbers."""
        ack_response = {
            "seq": negative_seq,
            "accepted": True,
            "duplicate": False,
            "errorCode": None
        }
        
        # Negative sequence numbers should be invalid
        assert self.client.validate_ack_response(ack_response) is False, f"Negative sequence number {negative_seq} should be invalid"

    def test_ack_response_field_type_validation(self):
        """Test ACK response validation with various field type combinations."""
        # Test all combinations of invalid field types
        invalid_field_combinations = [
            {"seq": "123", "accepted": True, "duplicate": False, "errorCode": None},
            {"seq": 123, "accepted": "true", "duplicate": False, "errorCode": None},
            {"seq": 123, "accepted": True, "duplicate": "false", "errorCode": None},
            {"seq": 123, "accepted": True, "duplicate": False, "errorCode": 123},
            {"seq": 123.5, "accepted": True, "duplicate": False, "errorCode": None},
            {"seq": None, "accepted": True, "duplicate": False, "errorCode": None},
        ]
        
        for invalid_ack in invalid_field_combinations:
            assert self.client.validate_ack_response(invalid_ack) is False, f"Invalid ACK should fail validation: {invalid_ack}"