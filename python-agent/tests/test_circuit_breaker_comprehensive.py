"""
Comprehensive unit tests for CircuitBreaker.

**Validates: Requirements 6.4**

Tests cover:
- Failure detection and threshold enforcement
- Circuit breaker state transitions (closed -> open -> half-open -> closed)
- Recovery timeout and half-open state behavior
- Error propagation and circuit breaker exceptions
- Thread safety for concurrent operations
"""
from __future__ import annotations

import time
from unittest.mock import Mock

import pytest

from utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class TestCircuitBreakerFailureDetection:
    """Test circuit breaker failure detection and threshold enforcement."""

    def test_circuit_breaker_starts_in_closed_state(self):
        """Verify circuit breaker starts in closed state."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)
        state = breaker.state()

        assert state["status"] == "closed"
        assert state["failureCount"] == 0

    def test_circuit_breaker_allows_successful_calls_in_closed_state(self):
        """Verify circuit breaker allows successful calls when closed."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        result = breaker.call(lambda: "success")

        assert result == "success"
        state = breaker.state()
        assert state["status"] == "closed"
        assert state["failureCount"] == 0

    def test_circuit_breaker_increments_failure_count_on_error(self):
        """Verify circuit breaker increments failure count on errors."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        state = breaker.state()
        assert state["status"] == "closed"
        assert state["failureCount"] == 2

    def test_circuit_breaker_opens_after_threshold_failures(self):
        """Verify circuit breaker opens after reaching failure threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        for i in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        state = breaker.state()
        assert state["status"] == "open"
        assert state["failureCount"] == 3
        assert state["openedAt"] is not None

    def test_circuit_breaker_rejects_calls_when_open(self):
        """Verify circuit breaker rejects calls when in open state."""
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_seconds=10)

        # Trigger circuit breaker to open
        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Next call should be rejected immediately
        with pytest.raises(CircuitBreakerOpenError, match="circuit breaker open: test"):
            breaker.call(lambda: "should not execute")


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery and half-open state behavior."""

    def test_circuit_breaker_transitions_to_half_open_after_timeout(self):
        """Verify circuit breaker transitions to half-open after recovery timeout."""
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_seconds=1)

        # Open the circuit breaker
        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should transition to half-open
        result = breaker.call(lambda: "recovered")

        assert result == "recovered"
        state = breaker.state()
        assert state["status"] == "closed"
        assert state["failureCount"] == 0

    def test_circuit_breaker_closes_on_successful_half_open_call(self):
        """Verify circuit breaker closes after successful call in half-open state."""
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_seconds=1)

        # Open the circuit breaker
        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Wait for recovery timeout
        time.sleep(1.1)

        # Successful call should close the circuit
        result = breaker.call(lambda: "success")

        assert result == "success"
        state = breaker.state()
        assert state["status"] == "closed"
        assert state["failureCount"] == 0
        assert state["openedAt"] is None

    def test_circuit_breaker_reopens_on_failed_half_open_call(self):
        """Verify circuit breaker reopens after failed call in half-open state."""
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_seconds=1)

        # Open the circuit breaker
        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Wait for recovery timeout
        time.sleep(1.1)

        # Failed call should reopen the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail again")))

        state = breaker.state()
        assert state["status"] == "open"

    def test_circuit_breaker_resets_failure_count_on_success(self):
        """Verify circuit breaker resets failure count after successful call."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        # Accumulate some failures
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["failureCount"] == 1

        # Successful call should reset count
        breaker.call(lambda: "success")

        state = breaker.state()
        assert state["failureCount"] == 0
        assert state["status"] == "closed"


class TestCircuitBreakerConfiguration:
    """Test circuit breaker configuration options."""

    def test_circuit_breaker_respects_custom_failure_threshold(self):
        """Verify circuit breaker respects custom failure threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        # Should not open after 4 failures
        for i in range(4):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "closed"

        # Should open after 5th failure
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "open"

    def test_circuit_breaker_enforces_minimum_failure_threshold(self):
        """Verify circuit breaker enforces minimum failure threshold of 1."""
        breaker = CircuitBreaker(name="test", failure_threshold=0)

        assert breaker.failure_threshold == 1

    def test_circuit_breaker_respects_custom_recovery_timeout(self):
        """Verify circuit breaker respects custom recovery timeout."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout_seconds=2)

        # Open the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Should still be open after 1 second
        time.sleep(1)
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "should not execute")

        # Should transition to half-open after 2 seconds
        time.sleep(1.1)
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"

    def test_circuit_breaker_enforces_minimum_recovery_timeout(self):
        """Verify circuit breaker enforces minimum recovery timeout of 1 second."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout_seconds=0.5)

        assert breaker.recovery_timeout_seconds == 1.0

    def test_circuit_breaker_uses_provided_name(self):
        """Verify circuit breaker uses provided name."""
        breaker = CircuitBreaker(name="my-service")

        state = breaker.state()
        assert state["name"] == "my-service"

    def test_circuit_breaker_defaults_to_default_name_when_empty(self):
        """Verify circuit breaker defaults to 'default' when name is empty."""
        breaker = CircuitBreaker(name="")

        state = breaker.state()
        assert state["name"] == "default"


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    def test_circuit_breaker_reset_closes_circuit(self):
        """Verify reset closes the circuit breaker."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)

        # Open the circuit
        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "open"

        # Reset the circuit
        breaker.reset()

        state = breaker.state()
        assert state["status"] == "closed"
        assert state["failureCount"] == 0
        assert state["openedAt"] is None

    def test_circuit_breaker_reset_allows_calls_after_reset(self):
        """Verify circuit breaker allows calls after reset."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)

        # Open the circuit
        for i in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Reset and verify calls work
        breaker.reset()

        result = breaker.call(lambda: "success after reset")
        assert result == "success after reset"


class TestCircuitBreakerErrorPropagation:
    """Test circuit breaker error propagation behavior."""

    def test_circuit_breaker_propagates_original_exception(self):
        """Verify circuit breaker propagates original exception from operation."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        with pytest.raises(ValueError, match="custom error"):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("custom error")))

    def test_circuit_breaker_propagates_exception_type(self):
        """Verify circuit breaker preserves exception type."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        class CustomException(Exception):
            pass

        with pytest.raises(CustomException):
            breaker.call(lambda: (_ for _ in ()).throw(CustomException("test")))

    def test_circuit_breaker_raises_specific_exception_when_open(self):
        """Verify circuit breaker raises CircuitBreakerOpenError when open."""
        breaker = CircuitBreaker(name="test-service", failure_threshold=1)

        # Open the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            breaker.call(lambda: "should not execute")

        assert "circuit breaker open: test-service" in str(exc_info.value)


class TestCircuitBreakerThreadSafety:
    """Test circuit breaker thread safety for concurrent operations."""

    def test_circuit_breaker_handles_concurrent_calls(self):
        """Verify circuit breaker handles concurrent calls correctly."""
        import threading

        breaker = CircuitBreaker(name="test", failure_threshold=5)
        success_count = {"value": 0}
        failure_count = {"value": 0}
        lock = threading.Lock()

        def make_call(should_fail):
            try:
                if should_fail:
                    breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
                else:
                    breaker.call(lambda: "success")
                with lock:
                    success_count["value"] += 1
            except (RuntimeError, CircuitBreakerOpenError):
                with lock:
                    failure_count["value"] += 1

        # Mix of successful and failing calls
        threads = []
        for i in range(20):
            thread = threading.Thread(target=make_call, args=(i % 3 == 0,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should have processed all calls
        assert success_count["value"] + failure_count["value"] == 20

    def test_circuit_breaker_state_transitions_are_thread_safe(self):
        """Verify circuit breaker state transitions are thread-safe."""
        import threading

        breaker = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout_seconds=1)

        def trigger_failures():
            for _ in range(3):
                try:
                    breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
                except RuntimeError:
                    pass

        def check_state():
            state = breaker.state()
            # State should always be valid
            assert state["status"] in ["closed", "open", "half_open"]
            assert isinstance(state["failureCount"], int)
            assert state["failureCount"] >= 0

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=trigger_failures))
            threads.append(threading.Thread(target=check_state))

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Circuit should be open after all failures
        final_state = breaker.state()
        assert final_state["status"] == "open"


class TestCircuitBreakerStateReporting:
    """Test circuit breaker state reporting functionality."""

    def test_circuit_breaker_state_includes_all_fields(self):
        """Verify circuit breaker state includes all required fields."""
        breaker = CircuitBreaker(name="test-service", failure_threshold=3)

        state = breaker.state()

        assert "name" in state
        assert "status" in state
        assert "failureCount" in state
        assert "openedAt" in state

    def test_circuit_breaker_state_opened_at_is_none_when_closed(self):
        """Verify openedAt is None when circuit is closed."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        state = breaker.state()
        assert state["openedAt"] is None

    def test_circuit_breaker_state_opened_at_is_set_when_open(self):
        """Verify openedAt is set when circuit opens."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        # Open the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        state = breaker.state()
        assert state["openedAt"] is not None
        assert isinstance(state["openedAt"], float)
        assert state["openedAt"] > 0


class TestCircuitBreakerEdgeCases:
    """Test circuit breaker edge cases and boundary conditions."""

    def test_circuit_breaker_handles_immediate_success_after_opening(self):
        """Verify circuit breaker handles immediate success after opening."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout_seconds=1)

        # Open the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Wait for recovery
        time.sleep(1.1)

        # Immediate success should close circuit
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"

        # Should accept subsequent calls
        result2 = breaker.call(lambda: "still working")
        assert result2 == "still working"

    def test_circuit_breaker_handles_multiple_recovery_attempts(self):
        """Verify circuit breaker handles multiple recovery attempts."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout_seconds=1)

        # Open the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # First recovery attempt fails
        time.sleep(1.1)
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("still failing")))

        # Second recovery attempt succeeds
        time.sleep(1.1)
        result = breaker.call(lambda: "finally recovered")
        assert result == "finally recovered"

    def test_circuit_breaker_handles_zero_duration_operations(self):
        """Verify circuit breaker handles operations that complete instantly."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        for _ in range(100):
            result = breaker.call(lambda: "instant")
            assert result == "instant"

        state = breaker.state()
        assert state["status"] == "closed"
        assert state["failureCount"] == 0
