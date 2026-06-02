"""
Test ACK response handling in ControlPlaneClient.

Tests Requirements 2.4 (Event ACK Protocol Compliance) and 2.5 (Event Deduplication).
"""

import json
import pytest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from io import BytesIO

from client.control_plane_client import ControlPlaneClient, ControlPlaneRequestError


class TestAckResponseHandling:
    """Test ACK response extraction and validation."""

    def setup_method(self):
        """Set up test client."""
        self.client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=10
        )

    def test_extract_ack_response_valid(self):
        """Test extracting valid ACK response."""
        response = {
            "success": True,
            "data": {
                "seq": 123,
                "accepted": True,
                "duplicate": False,
                "errorCode": None
            }
        }
        
        ack = self.client.extract_ack_response(response)
        
        assert ack is not None
        assert ack["seq"] == 123
        assert ack["accepted"] is True
        assert ack["duplicate"] is False
        assert ack["errorCode"] is None

    def test_extract_ack_response_with_error(self):
        """Test extracting ACK response with error code."""
        response = {
            "success": True,
            "data": {
                "seq": 0,
                "accepted": False,
                "duplicate": False,
                "errorCode": "TASK_NOT_FOUND"
            }
        }
        
        ack = self.client.extract_ack_response(response)
        
        assert ack is not None
        assert ack["seq"] == 0
        assert ack["accepted"] is False
        assert ack["duplicate"] is False
        assert ack["errorCode"] == "TASK_NOT_FOUND"

    def test_extract_ack_response_duplicate(self):
        """Test extracting ACK response for duplicate event."""
        response = {
            "success": True,
            "data": {
                "seq": 456,
                "accepted": True,
                "duplicate": True,
                "errorCode": None
            }
        }
        
        ack = self.client.extract_ack_response(response)
        
        assert ack is not None
        assert ack["seq"] == 456
        assert ack["accepted"] is True
        assert ack["duplicate"] is True
        assert ack["errorCode"] is None

    def test_extract_ack_response_invalid_format(self):
        """Test extracting ACK response with invalid format."""
        invalid_responses = [
            None,
            {},
            {"success": True},
            {"success": True, "data": None},
            {"success": True, "data": {}},
            {"success": True, "data": {"seq": "invalid"}},
            {"success": True, "data": {"seq": 123, "accepted": "invalid"}},
            {"success": True, "data": {"seq": 123, "accepted": True, "duplicate": "invalid"}},
        ]
        
        for response in invalid_responses:
            ack = self.client.extract_ack_response(response)
            assert ack is None, f"Should return None for invalid response: {response}"

    def test_validate_ack_response_valid(self):
        """Test validating valid ACK responses."""
        valid_acks = [
            {"seq": 123, "accepted": True, "duplicate": False, "errorCode": None},
            {"seq": 0, "accepted": False, "duplicate": False, "errorCode": "TASK_NOT_FOUND"},
            {"seq": 456, "accepted": True, "duplicate": True, "errorCode": None},
        ]
        
        for ack in valid_acks:
            assert self.client.validate_ack_response(ack) is True

    def test_validate_ack_response_with_expected_seq(self):
        """Test validating ACK response with expected sequence number."""
        ack = {"seq": 123, "accepted": True, "duplicate": False, "errorCode": None}
        
        assert self.client.validate_ack_response(ack, expected_seq=123) is True
        assert self.client.validate_ack_response(ack, expected_seq=456) is False

    def test_validate_ack_response_invalid(self):
        """Test validating invalid ACK responses."""
        invalid_acks = [
            None,
            {},
            {"seq": "invalid", "accepted": True, "duplicate": False},
            {"seq": 123, "accepted": "invalid", "duplicate": False},
            {"seq": 123, "accepted": True, "duplicate": "invalid"},
            {"seq": 123, "accepted": True, "duplicate": False, "errorCode": 123},
        ]
        
        for ack in invalid_acks:
            assert self.client.validate_ack_response(ack) is False

    @patch('client.control_plane_client.request.urlopen')
    def test_publish_event_with_ack_success(self, mock_urlopen):
        """Test successful event publishing with ACK response."""
        # Mock successful response with ACK
        response_data = {
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
        mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
        ack = self.client.publish_event_with_ack("task-123", event)
        
        assert ack is not None
        assert ack["seq"] == 123
        assert ack["accepted"] is True
        assert ack["duplicate"] is False
        assert ack["errorCode"] is None

    @patch('client.control_plane_client.request.urlopen')
    def test_publish_event_with_ack_duplicate(self, mock_urlopen):
        """Test event publishing with duplicate ACK response."""
        # Mock duplicate response
        response_data = {
            "success": True,
            "data": {
                "seq": 123,
                "accepted": True,
                "duplicate": True,
                "errorCode": None
            }
        }
        
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
        ack = self.client.publish_event_with_ack("task-123", event)
        
        assert ack is not None
        assert ack["seq"] == 123
        assert ack["accepted"] is True
        assert ack["duplicate"] is True
        assert ack["errorCode"] is None

    @patch('client.control_plane_client.request.urlopen')
    def test_publish_event_with_ack_not_accepted(self, mock_urlopen):
        """Test event publishing with not accepted ACK response."""
        # Mock not accepted response
        response_data = {
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
        mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
        
        # Should raise exception for non-retryable error
        with pytest.raises(ControlPlaneRequestError) as exc_info:
            self.client.publish_event_with_ack("task-123", event)
        
        assert "Event not accepted by Control Plane: TASK_NOT_FOUND" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @patch('client.control_plane_client.request.urlopen')
    def test_publish_event_with_ack_retryable_error(self, mock_urlopen):
        """Test event publishing with retryable error ACK response."""
        # Mock processing error response (retryable)
        response_data = {
            "success": True,
            "data": {
                "seq": 0,
                "accepted": False,
                "duplicate": False,
                "errorCode": "PROCESSING_ERROR"
            }
        }
        
        mock_response = Mock()
        mock_response.getcode.return_value = 500
        mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
        
        # Should raise exception but mark as retryable
        with pytest.raises(ControlPlaneRequestError) as exc_info:
            self.client.publish_event_with_ack("task-123", event, max_attempts=1)
        
        assert "Event not accepted by Control Plane: PROCESSING_ERROR" in str(exc_info.value)
        assert exc_info.value.retryable is True

    @patch('client.control_plane_client.request.urlopen')
    def test_publish_event_with_ack_invalid_response(self, mock_urlopen):
        """Test event publishing with invalid ACK response format."""
        # Mock invalid response format
        response_data = {
            "success": True,
            "data": "invalid"  # Should be object with ACK fields
        }
        
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
        
        # Should raise exception for invalid ACK format
        with pytest.raises(ControlPlaneRequestError) as exc_info:
            self.client.publish_event_with_ack("task-123", event, max_attempts=1)
        
        assert "Invalid ACK response format from Control Plane" in str(exc_info.value)
        assert exc_info.value.retryable is True

    def test_publish_event_with_retry_result_includes_ack(self):
        """Test that retry result includes ACK response data."""
        with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
            # Mock successful response with ACK
            response_data = {
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
            mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
            result = self.client.publish_event_with_retry_result("task-123", event)
            
            assert result.response is not None
            assert result.attempts == 1
            assert result.final_error is None
            assert result.ack_response is not None
            assert result.ack_response["seq"] == 123
            assert result.ack_response["accepted"] is True
            assert result.ack_response["duplicate"] is False
            assert result.ack_response["errorCode"] is None


class TestAckResponseErrorClassification:
    """Test error classification for ACK responses."""

    def setup_method(self):
        """Set up test client."""
        self.client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=10
        )

    def test_non_retryable_error_codes(self):
        """Test that certain error codes are classified as non-retryable."""
        non_retryable_errors = [
            "INVALID_NODE_ID",
            "NODE_NOT_REGISTERED", 
            "MISSING_EVENT_ID",
            "TASK_NOT_FOUND"
        ]
        
        for error_code in non_retryable_errors:
            with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
                response_data = {
                    "success": True,
                    "data": {
                        "seq": 0,
                        "accepted": False,
                        "duplicate": False,
                        "errorCode": error_code
                    }
                }
                
                mock_response = Mock()
                mock_response.getcode.return_value = 400
                mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
                
                with pytest.raises(ControlPlaneRequestError) as exc_info:
                    self.client.publish_event_with_ack("task-123", event, max_attempts=1)
                
                assert exc_info.value.retryable is False, f"Error {error_code} should be non-retryable"

    def test_retryable_error_codes(self):
        """Test that certain error codes are classified as retryable."""
        retryable_errors = [
            "PROCESSING_ERROR",
            "UNKNOWN_ERROR"
        ]
        
        for error_code in retryable_errors:
            with patch('client.control_plane_client.request.urlopen') as mock_urlopen:
                response_data = {
                    "success": True,
                    "data": {
                        "seq": 0,
                        "accepted": False,
                        "duplicate": False,
                        "errorCode": error_code
                    }
                }
                
                mock_response = Mock()
                mock_response.getcode.return_value = 500
                mock_response.read.return_value = json.dumps(response_data).encode('utf-8')
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                event = {"type": "TASK_STARTED", "eventId": "evt-123", "seq": 123}
                
                with pytest.raises(ControlPlaneRequestError) as exc_info:
                    self.client.publish_event_with_ack("task-123", event, max_attempts=1)
                
                assert exc_info.value.retryable is True, f"Error {error_code} should be retryable"