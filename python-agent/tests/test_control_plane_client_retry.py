"""
Tests for enhanced control plane client with retry and backoff functionality.

Tests Property 4: Event Delivery Retry with Backoff
Validates: Requirements 2.2
"""

import json
import time
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from client.control_plane_client import ControlPlaneClient, ControlPlaneRequestError, PublishEventResult
from utils.circuit_breaker import CircuitBreakerOpenError, CircuitBreaker
from utils.observability import TaskObservability


class TestControlPlaneClientRetry:
    """Test suite for control plane client retry and backoff functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        self.task_id = "test-task-123"
        self.test_event = {
            "eventId": "evt_" + "a" * 32,
            "eventVersion": 1,
            "taskId": self.task_id,
            "assistant": "test-assistant",
            "type": "TASK_STARTED",
            "timestamp": "2024-01-01T00:00:00Z",
            "seq": 1,
            "payload": {"status": "started"}
        }
    
    def test_successful_delivery_first_attempt(self):
        """Test successful event delivery on first attempt."""
        with patch.object(self.client, 'publish_event') as mock_publish:
            mock_publish.return_value = {
                "success": True,
                "data": {
                    "seq": 1,
                    "accepted": True,
                    "duplicate": False,
                    "errorCode": None
                }
            }
            
            result = self.client.publish_event_with_retry_result(
                self.task_id, 
                self.test_event
            )
            
            assert result.response is not None
            assert result.attempts == 1
            assert result.total_delay_seconds == 0.0
            assert not result.circuit_breaker_triggered
            assert result.final_error is None
            assert result.ack_response is not None
            assert result.ack_response["seq"] == 1
            assert result.ack_response["accepted"] is True
            mock_publish.assert_called_once_with(self.task_id, self.test_event)
    
    def test_exponential_backoff_sequence(self):
        """Test exponential backoff timing: 1s, 2s, 4s, 8s, 16s."""
        # Create a fresh client with higher circuit breaker threshold to test full sequence
        fresh_client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        # Override circuit breaker with higher threshold for this test
        fresh_client._event_circuit_breaker = CircuitBreaker(
            name="test_circuit_breaker",
            failure_threshold=10,  # High threshold to avoid interference
            recovery_timeout_seconds=60.0
        )
        
        with patch.object(fresh_client, 'publish_event') as mock_publish:
            with patch('time.sleep') as mock_sleep:
                # Fail first 4 attempts, succeed on 5th
                mock_publish.side_effect = [
                    ControlPlaneRequestError("Connection failed", retryable=True),
                    ControlPlaneRequestError("Connection failed", retryable=True),
                    ControlPlaneRequestError("Connection failed", retryable=True),
                    ControlPlaneRequestError("Connection failed", retryable=True),
                    {
                        "success": True,
                        "data": {
                            "seq": 1,
                            "accepted": True,
                            "duplicate": False,
                            "errorCode": None
                        }
                    }
                ]
                
                result = fresh_client.publish_event_with_retry_result(
                    self.task_id,
                    self.test_event,
                    max_attempts=5
                )
                
                # Verify exponential backoff delays: 1s, 2s, 4s, 8s
                expected_delays = [1.0, 2.0, 4.0, 8.0]
                actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
                assert actual_delays == expected_delays
                
                assert result.attempts == 5
                assert result.response is not None
                assert result.ack_response is not None
                assert result.ack_response["seq"] == 1
                assert result.ack_response["accepted"] is True
                assert result.total_delay_seconds == sum(expected_delays)
    
    def test_maximum_attempts_enforcement(self):
        """Test that maximum attempts is enforced at 5 per requirement."""
        # Create a fresh client to avoid circuit breaker state from other tests
        fresh_client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        with patch.object(fresh_client, 'publish_event') as mock_publish:
            mock_publish.side_effect = ControlPlaneRequestError("Connection failed", retryable=True)
            
            # Try to set max_attempts > 5, should be capped at 5
            result = fresh_client.publish_event_with_retry_result(
                self.task_id,
                self.test_event,
                max_attempts=10  # Should be capped at 5
            )
            
            assert result.attempts == 5
            # Circuit breaker will open after 3 failures, so we expect 3 calls
            assert mock_publish.call_count == 3
            assert result.response is None
            assert result.circuit_breaker_triggered
    
    def test_non_retryable_error_stops_immediately(self):
        """Test that non-retryable errors stop retry attempts immediately."""
        # Create a fresh client to avoid circuit breaker state from other tests
        fresh_client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token",
            timeout_seconds=5
        )
        
        with patch.object(fresh_client, 'publish_event') as mock_publish:
            mock_publish.side_effect = ControlPlaneRequestError("Bad request", retryable=False)
            
            result = fresh_client.publish_event_with_retry_result(
                self.task_id,
                self.test_event,
                max_attempts=5
            )
            
            # Should only attempt once for non-retryable error
            mock_publish.assert_called_once()
            
            # Verify result contains the error
            assert result.response is None
            assert result.attempts == 1
            assert result.final_error is not None
            assert isinstance(result.final_error, ControlPlaneRequestError)
            assert not result.final_error.retryable
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration blocks requests when open."""
        # First, trigger circuit breaker by causing failures
        with patch.object(self.client, 'publish_event') as mock_publish:
            mock_publish.side_effect = ControlPlaneRequestError("Service unavailable", retryable=True)
            
            # Cause 3 failures to open circuit breaker
            for _ in range(3):
                try:
                    self.client.publish_event_with_retry_result(
                        self.task_id,
                        self.test_event,
                        max_attempts=1
                    )
                except ControlPlaneRequestError:
                    pass
            
            # Now circuit breaker should be open
            result = self.client.publish_event_with_retry_result(
                self.task_id,
                self.test_event,
                max_attempts=5
            )
            
            assert result.circuit_breaker_triggered
            assert isinstance(result.final_error, CircuitBreakerOpenError)
            assert result.response is None
    
    def test_observability_integration(self):
        """Test integration with observability for structured logging."""
        observability = TaskObservability(
            task_id=self.task_id,
            trace_id="trace-123",
            run_id="run-456",
            engine="test"
        )
        
        with patch.object(self.client, 'publish_event') as mock_publish:
            mock_publish.return_value = {
                "success": True,
                "data": {
                    "seq": 1,
                    "accepted": True,
                    "duplicate": False,
                    "errorCode": None
                }
            }
            
            result = self.client.publish_event_with_retry_result(
                self.task_id,
                self.test_event,
                observability=observability
            )
            
            assert result.response is not None
            assert result.ack_response is not None
            assert result.ack_response["seq"] == 1
            assert result.ack_response["accepted"] is True
            assert result.attempts == 1
    
    def test_metrics_tracking(self):
        """Test that event delivery metrics are properly tracked."""
        # Reset metrics
        self.client.reset_metrics()
        
        with patch.object(self.client, 'publish_event') as mock_publish:
            # Successful delivery
            mock_publish.return_value = {
                "success": True,
                "data": {
                    "seq": 1,
                    "accepted": True,
                    "duplicate": False,
                    "errorCode": None
                }
            }
            self.client.publish_event_with_retry_result(self.task_id, self.test_event)
            
            # Failed delivery
            mock_publish.side_effect = ControlPlaneRequestError("Connection failed", retryable=True)
            result = self.client.publish_event_with_retry_result(
                self.task_id, 
                self.test_event,
                max_attempts=2
            )
            
            metrics = self.client.get_event_delivery_metrics()
            
            assert metrics["totalAttempts"] == 3  # 1 success + 2 failed attempts
            assert metrics["successfulDeliveries"] == 1
            assert metrics["failedDeliveries"] == 1
            assert metrics["successRate"] > 0
            assert metrics["failureRate"] > 0
    
    def test_structured_logging_context(self):
        """Test that structured logging includes proper context."""
        with patch.object(self.client._logger, 'info') as mock_log_info:
            with patch.object(self.client, 'publish_event') as mock_publish:
                mock_publish.return_value = {
                    "success": True,
                    "data": {
                        "seq": 1,
                        "accepted": True,
                        "duplicate": False,
                        "errorCode": None
                    }
                }
                
                self.client.publish_event_with_retry_result(
                    self.task_id,
                    self.test_event
                )
                
                # Verify structured logging was called with proper context
                assert mock_log_info.called
                log_call = mock_log_info.call_args_list[0]
                extra_context = log_call.kwargs.get('extra', {})
                
                assert extra_context.get('taskId') == self.task_id
                assert extra_context.get('eventType') == 'TASK_STARTED'
                assert extra_context.get('maxAttempts') == 5
                assert extra_context.get('initialBackoff') == 1.0
    
    def test_convenience_method_returns_response_only(self):
        """Test that convenience method returns only the response."""
        with patch.object(self.client, 'publish_event') as mock_publish:
            mock_publish.return_value = {
                "success": True,
                "data": {
                    "seq": 1,
                    "accepted": True,
                    "duplicate": False,
                    "errorCode": None
                }
            }
            
            response = self.client.publish_event_with_retry(
                self.task_id,
                self.test_event
            )
            
            assert response is not None
    
    def test_initial_backoff_minimum_enforced(self):
        """Test that initial backoff has minimum of 1.0 seconds per requirement."""
        with patch.object(self.client, 'publish_event') as mock_publish:
            with patch('time.sleep') as mock_sleep:
                mock_publish.side_effect = [
                    ControlPlaneRequestError("Connection failed", retryable=True),
                    {
                        "success": True,
                        "data": {
                            "seq": 1,
                            "accepted": True,
                            "duplicate": False,
                            "errorCode": None
                        }
                    }
                ]
                
                # Try to set initial backoff < 1.0, should be enforced to 1.0
                self.client.publish_event_with_retry_result(
                    self.task_id,
                    self.test_event,
                    initial_backoff_seconds=0.5  # Should be enforced to 1.0
                )
                
                # First retry should use 1.0 second delay (minimum enforced)
                mock_sleep.assert_called_once_with(1.0)


class TestControlPlaneClientRetryProperty:
    """Property-based tests for retry behavior."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token"
        )
    
    def test_property_retry_with_exponential_backoff(self):
        """
        Property 4: Event Delivery Retry with Backoff
        
        For any Control_Plane unavailability scenario, the Python_Agent SHALL retry 
        event delivery with exponential backoff up to the maximum retry limit.
        
        Validates: Requirements 2.2
        """
        # Create a fresh client with higher circuit breaker threshold to test full sequence
        fresh_client = ControlPlaneClient(
            base_url="http://localhost:8058",
            agent_token="test-token"
        )
        # Override circuit breaker with higher threshold for this test
        fresh_client._event_circuit_breaker = CircuitBreaker(
            name="test_circuit_breaker",
            failure_threshold=10,  # High threshold to avoid interference
            recovery_timeout_seconds=60.0
        )
        
        task_id = "test-task-property"
        event = {
            "eventId": "evt_" + "b" * 32,
            "eventVersion": 1,
            "taskId": task_id,
            "assistant": "test-assistant",
            "type": "TASK_PROGRESS",
            "timestamp": "2024-01-01T00:00:00Z",
            "seq": 1,
            "payload": {"progress": 50}
        }
        
        with patch.object(fresh_client, 'publish_event') as mock_publish:
            with patch('time.sleep') as mock_sleep:
                # Simulate Control Plane unavailability for all attempts
                mock_publish.side_effect = ControlPlaneRequestError(
                    "Control Plane unavailable", 
                    retryable=True
                )
                
                result = fresh_client.publish_event_with_retry_result(
                    task_id,
                    event,
                    max_attempts=5
                )
                
                # With high circuit breaker threshold, we should get full retry sequence
                expected_delays = [1.0, 2.0, 4.0, 8.0]  # 1s, 2s, 4s, 8s
                actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
                
                # Property: Exponential backoff SHALL be used
                assert actual_delays == expected_delays, f"Expected {expected_delays}, got {actual_delays}"
                
                # Property: Maximum 5 attempts SHALL be enforced
                assert mock_publish.call_count == 5, f"Expected 5 attempts, got {mock_publish.call_count}"
                
                # Property: Total backoff time follows exponential pattern
                total_backoff = sum(actual_delays)
                expected_total = sum(expected_delays)
                assert total_backoff == expected_total, f"Expected total backoff {expected_total}s, got {total_backoff}s"