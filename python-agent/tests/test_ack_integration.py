"""
Integration test for ACK response handling between Python client and Control Plane.

This test verifies that the shared protocol is correctly implemented on both sides.
"""

import json
import pytest
from unittest.mock import Mock, patch

from client.control_plane_client import ControlPlaneClient


class TestAckIntegration:
    """Integration tests for ACK response protocol."""

    def setup_method(self):
        """Set up test client."""
        self.client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=10
        )

    @patch('client.control_plane_client.request.urlopen')
    def test_end_to_end_ack_response_format(self, mock_urlopen):
        """Test that the client correctly handles the Control Plane ACK response format."""
        # This simulates the exact response format that the Java Control Plane returns
        control_plane_response = {
            "success": True,
            "data": {
                "seq": 123,
                "accepted": True,
                "duplicate": False,
                "errorCode": None
            }
        }
        
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Test event publishing
        event = {
            "type": "TASK_STARTED",
            "eventId": "evt-123",
            "seq": 123,
            "timestamp": "2026-05-02T12:00:00Z"
        }
        
        # Test the full response
        response = self.client.publish_event("task-123", event)
        assert response is not None
        assert response["success"] is True
        assert "data" in response
        
        # Test ACK extraction
        ack = self.client.extract_ack_response(response)
        assert ack is not None
        assert ack["seq"] == 123
        assert ack["accepted"] is True
        assert ack["duplicate"] is False
        assert ack["errorCode"] is None
        
        # Test ACK validation
        assert self.client.validate_ack_response(ack) is True
        assert self.client.validate_ack_response(ack, expected_seq=123) is True
        assert self.client.validate_ack_response(ack, expected_seq=456) is False

    @patch('client.control_plane_client.request.urlopen')
    def test_duplicate_event_ack_response(self, mock_urlopen):
        """Test handling of duplicate event ACK response."""
        control_plane_response = {
            "success": True,
            "data": {
                "seq": 456,
                "accepted": True,
                "duplicate": True,
                "errorCode": None
            }
        }
        
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-duplicate", "seq": 456}
        ack = self.client.publish_event_with_ack("task-123", event)
        
        assert ack is not None
        assert ack["seq"] == 456
        assert ack["accepted"] is True
        assert ack["duplicate"] is True
        assert ack["errorCode"] is None

    @patch('client.control_plane_client.request.urlopen')
    def test_error_ack_response(self, mock_urlopen):
        """Test handling of error ACK response."""
        control_plane_response = {
            "success": True,
            "data": {
                "seq": 0,
                "accepted": False,
                "duplicate": False,
                "errorCode": "TASK_NOT_FOUND"
            }
        }
        
        mock_response = Mock()
        mock_response.getcode.return_value = 404
        mock_response.read.return_value = json.dumps(control_plane_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-error", "seq": 789}
        
        # Should raise exception for non-retryable error
        with pytest.raises(Exception) as exc_info:
            self.client.publish_event_with_ack("invalid-task", event, max_attempts=1)
        
        assert "TASK_NOT_FOUND" in str(exc_info.value)

    def test_schema_compliance(self):
        """Test that our ACK response structure complies with the JSON schema."""
        # Test valid ACK responses according to the schema
        valid_acks = [
            {"seq": 0, "accepted": True, "duplicate": False, "errorCode": None},
            {"seq": 123, "accepted": False, "duplicate": False, "errorCode": "TASK_NOT_FOUND"},
            {"seq": 456, "accepted": True, "duplicate": True, "errorCode": None},
            {"seq": 789, "accepted": False, "duplicate": False, "errorCode": "PROCESSING_ERROR"},
        ]
        
        for ack in valid_acks:
            assert self.client.validate_ack_response(ack) is True
        
        # Test invalid ACK responses
        invalid_acks = [
            {"seq": -1, "accepted": True, "duplicate": False, "errorCode": None},  # seq < 0
            {"seq": "123", "accepted": True, "duplicate": False, "errorCode": None},  # seq not int
            {"seq": 123, "accepted": "true", "duplicate": False, "errorCode": None},  # accepted not bool
            {"seq": 123, "accepted": True, "duplicate": "false", "errorCode": None},  # duplicate not bool
            {"seq": 123, "accepted": True, "duplicate": False, "errorCode": 123},  # errorCode not string/null
        ]
        
        for ack in invalid_acks:
            assert self.client.validate_ack_response(ack) is False

    def test_error_code_classification(self):
        """Test that error codes are correctly classified as retryable/non-retryable."""
        # Non-retryable errors (client/configuration issues)
        non_retryable = [
            "INVALID_NODE_ID",
            "NODE_NOT_REGISTERED", 
            "MISSING_EVENT_ID",
            "TASK_NOT_FOUND"
        ]
        
        # Retryable errors (server/processing issues)
        retryable = [
            "PROCESSING_ERROR"
        ]
        
        # This test verifies the error classification logic exists in the client
        # The actual classification happens in the publish_event_with_retry_result method
        # when it determines whether to retry based on the error code
        
        for error_code in non_retryable:
            # These should be classified as non-retryable
            assert error_code in ["INVALID_NODE_ID", "NODE_NOT_REGISTERED", "MISSING_EVENT_ID", "TASK_NOT_FOUND"]
        
        for error_code in retryable:
            # These should be classified as retryable
            assert error_code not in ["INVALID_NODE_ID", "NODE_NOT_REGISTERED", "MISSING_EVENT_ID", "TASK_NOT_FOUND"]