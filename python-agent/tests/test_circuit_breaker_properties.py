"""
Property-based tests for circuit breaker behavior.

Task 14.4: Write property tests for circuit breaker behavior
Property 21: Circuit Breaker Activation

For any sequence of LLM service failures, the Circuit_Breaker SHALL open
after 3 consecutive failures and provide fallback mechanisms.

**Validates: Requirements 7.2, 7.3**
"""
from __future__ import annotations

import time

import pytest
from hypothesis import assume, given, settings, strategies as st

from utils.circuit_breaker import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_RECOVERY_TIMEOUT_SECONDS,
    CircuitBreaker,
    CircuitBreakerOpenError,
    make_llm_circuit_breaker,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

#: Failure counts that should NOT yet open the circuit (1 or 2 failures).
sub_threshold_failures_strategy = st.integers(
    min_value=1, max_value=DEFAULT_FAILURE_THRESHOLD - 1
)

#: Failure counts that SHOULD open the circuit (≥ 3 failures).
at_or_above_threshold_strategy = st.integers(
    min_value=DEFAULT_FAILURE_THRESHOLD, max_value=DEFAULT_FAILURE_THRESHOLD + 10
)

#: Arbitrary positive failure thresholds for parameterised tests.
failure_threshold_strategy = st.integers(min_value=1, max_value=10)

#: Arbitrary service names.
service_name_strategy = st.text(
    min_size=1,
    max_size=40,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc")),
)

#: Sequences of booleans representing success (True) or failure (False).
call_sequence_strategy = st.lists(st.booleans(), min_size=1, max_size=20)


# ---------------------------------------------------------------------------
# Property 21: Circuit Breaker Activation
# ---------------------------------------------------------------------------


class TestProperty21CircuitBreakerActivation:
    """
    **Property 21: Circuit Breaker Activation**

    For any sequence of LLM service failures, the Circuit_Breaker SHALL open
    after 3 consecutive failures and provide fallback mechanisms.

    **Validates: Requirements 7.2, 7.3**
    """

    # ------------------------------------------------------------------
    # Default threshold is 3 (Req 7.2)
    # ------------------------------------------------------------------

    def test_property_21_default_failure_threshold_is_3(self):
        """
        **Property 21 – The default failure threshold SHALL be 3.**

        **Validates: Requirements 7.2**
        """
        assert DEFAULT_FAILURE_THRESHOLD == 3
        breaker = CircuitBreaker(name="test")
        assert breaker.failure_threshold == 3

    def test_property_21_circuit_opens_after_exactly_3_consecutive_failures(self):
        """
        **Property 21 – The circuit SHALL open after exactly 3 consecutive failures.**

        **Validates: Requirements 7.2**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=3)

        # Two failures — circuit must remain closed
        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "closed", "Circuit must stay closed after 2 failures"

        # Third failure — circuit must open
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "open", "Circuit must open after 3 consecutive failures"

    def test_property_21_circuit_open_rejects_calls_immediately(self):
        """
        **Property 21 – When the circuit is open, calls SHALL be rejected
        immediately (fail-fast fallback).**

        **Validates: Requirements 7.3**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=3, recovery_timeout_seconds=60)

        # Open the circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Subsequent calls must be rejected without executing the operation
        executed = []

        def operation():
            executed.append(True)
            return "should not run"

        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(operation)

        assert not executed, "Operation must NOT be executed when circuit is open"

    # ------------------------------------------------------------------
    # Parameterised threshold tests
    # ------------------------------------------------------------------

    @given(failure_threshold_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_21_circuit_opens_at_configured_threshold(self, threshold: int):
        """
        **Property 21 – For any configured failure threshold N, the circuit
        SHALL open after exactly N consecutive failures.**

        **Validates: Requirements 7.2**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=threshold)

        # Accumulate threshold - 1 failures; circuit must stay closed
        for _ in range(threshold - 1):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "closed", (
            f"Circuit must stay closed after {threshold - 1} failures "
            f"(threshold={threshold})"
        )

        # The Nth failure must open the circuit
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "open", (
            f"Circuit must open after {threshold} consecutive failures"
        )

    @given(sub_threshold_failures_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_21_circuit_stays_closed_below_threshold(self, failure_count: int):
        """
        **Property 21 – For any failure count below the threshold, the circuit
        SHALL remain closed.**

        **Validates: Requirements 7.2**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=DEFAULT_FAILURE_THRESHOLD)

        for _ in range(failure_count):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        state = breaker.state()
        assert state["status"] == "closed", (
            f"Circuit must stay closed after {failure_count} failures "
            f"(threshold={DEFAULT_FAILURE_THRESHOLD})"
        )
        assert state["failureCount"] == failure_count

    @given(at_or_above_threshold_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_21_circuit_opens_at_or_above_threshold(self, failure_count: int):
        """
        **Property 21 – For any failure count ≥ threshold, the circuit SHALL
        be open.**

        **Validates: Requirements 7.2**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=DEFAULT_FAILURE_THRESHOLD)

        for _ in range(failure_count):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except (RuntimeError, CircuitBreakerOpenError):
                pass

        assert breaker.state()["status"] == "open", (
            f"Circuit must be open after {failure_count} failures "
            f"(threshold={DEFAULT_FAILURE_THRESHOLD})"
        )

    # ------------------------------------------------------------------
    # Success resets failure count
    # ------------------------------------------------------------------

    @given(sub_threshold_failures_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_21_success_resets_failure_count(self, failure_count: int):
        """
        **Property 21 – A successful call SHALL reset the consecutive failure
        count, preventing the circuit from opening.**

        **Validates: Requirements 7.2**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=DEFAULT_FAILURE_THRESHOLD)

        # Accumulate some failures (below threshold)
        for _ in range(failure_count):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # A success resets the count
        result = breaker.call(lambda: "ok")
        assert result == "ok"

        state = breaker.state()
        assert state["failureCount"] == 0, "Failure count must be reset after success"
        assert state["status"] == "closed"

    # ------------------------------------------------------------------
    # Fallback mechanism: CircuitBreakerOpenError is raised
    # ------------------------------------------------------------------

    @given(service_name_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_21_open_circuit_raises_circuit_breaker_open_error(self, name: str):
        """
        **Property 21 – When the circuit is open, CircuitBreakerOpenError SHALL
        be raised to signal the fallback path.**

        **Validates: Requirements 7.3**
        """
        assume(name.strip())
        breaker = CircuitBreaker(
            name=name.strip(),
            failure_threshold=DEFAULT_FAILURE_THRESHOLD,
            recovery_timeout_seconds=60,
        )

        # Open the circuit
        for _ in range(DEFAULT_FAILURE_THRESHOLD):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        # Must raise CircuitBreakerOpenError (not a generic RuntimeError)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            breaker.call(lambda: "should not run")

        assert name.strip() in str(exc_info.value), (
            "CircuitBreakerOpenError must include the service name"
        )

    @given(call_sequence_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_21_consecutive_failures_determine_open_state(
        self, call_sequence: list[bool]
    ):
        """
        **Property 21 – For any sequence of successes and failures, the circuit
        SHALL open after N consecutive failures (N = threshold) and remain open
        until the recovery timeout elapses.**

        **Validates: Requirements 7.2**
        """
        threshold = DEFAULT_FAILURE_THRESHOLD
        breaker = CircuitBreaker(name="llm-test", failure_threshold=threshold)

        # Simulate the call sequence and track whether the circuit opened
        circuit_opened = False
        for success in call_sequence:
            try:
                if success:
                    breaker.call(lambda: "ok")
                else:
                    breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except CircuitBreakerOpenError:
                # Circuit was already open — this is expected once opened
                circuit_opened = True
            except RuntimeError:
                pass

        # Determine whether the circuit should be open by simulating the
        # state machine: track consecutive failures, reset on success,
        # and mark as open once threshold is reached.
        simulated_open = False
        consecutive = 0
        for success in call_sequence:
            if simulated_open:
                # Once open, all calls are rejected — state doesn't change
                break
            if success:
                consecutive = 0
            else:
                consecutive += 1
                if consecutive >= threshold:
                    simulated_open = True

        actual_status = breaker.state()["status"]

        if simulated_open:
            assert actual_status == "open", (
                f"Circuit must be open. Sequence: {call_sequence}"
            )
        else:
            assert actual_status == "closed", (
                f"Circuit must be closed when threshold not reached. "
                f"Sequence: {call_sequence}"
            )

    # ------------------------------------------------------------------
    # make_llm_circuit_breaker factory
    # ------------------------------------------------------------------

    def test_property_21_make_llm_circuit_breaker_uses_default_threshold(self):
        """
        **Property 21 – make_llm_circuit_breaker SHALL create a breaker with
        failure_threshold=3 by default.**

        **Validates: Requirements 7.2**
        """
        breaker = make_llm_circuit_breaker("intent-llm")
        assert breaker.failure_threshold == DEFAULT_FAILURE_THRESHOLD

    def test_property_21_make_llm_circuit_breaker_uses_default_recovery_timeout(self):
        """
        **Property 21 – make_llm_circuit_breaker SHALL create a breaker with
        recovery_timeout_seconds=60 by default.**

        **Validates: Requirements 7.4**
        """
        breaker = make_llm_circuit_breaker("planner-llm")
        assert breaker.recovery_timeout_seconds == DEFAULT_RECOVERY_TIMEOUT_SECONDS
        assert breaker.recovery_timeout_seconds == 60.0

    @given(service_name_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_21_make_llm_circuit_breaker_opens_after_3_failures(
        self, name: str
    ):
        """
        **Property 21 – For any LLM service name, make_llm_circuit_breaker SHALL
        produce a breaker that opens after 3 consecutive failures.**

        **Validates: Requirements 7.2, 7.3**
        """
        assume(name.strip())
        breaker = make_llm_circuit_breaker(name.strip())

        for _ in range(DEFAULT_FAILURE_THRESHOLD):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("llm unavailable")))

        assert breaker.state()["status"] == "open"

        # Verify fail-fast behaviour
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "should not run")

    # ------------------------------------------------------------------
    # Default recovery timeout is 60 seconds (Req 7.4)
    # ------------------------------------------------------------------

    def test_property_21_default_recovery_timeout_is_60_seconds(self):
        """
        **Property 21 – The default recovery timeout SHALL be 60 seconds.**

        **Validates: Requirements 7.4**
        """
        assert DEFAULT_RECOVERY_TIMEOUT_SECONDS == 60.0
        breaker = CircuitBreaker(name="test")
        assert breaker.recovery_timeout_seconds == 60.0

    def test_property_21_circuit_transitions_to_half_open_after_recovery_timeout(self):
        """
        **Property 21 – After the recovery timeout elapses, the circuit SHALL
        transition to half-open and allow a probe call.**

        **Validates: Requirements 7.4**
        """
        breaker = CircuitBreaker(name="llm-test", failure_threshold=3, recovery_timeout_seconds=1)

        # Open the circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        assert breaker.state()["status"] == "open"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Probe call should succeed and close the circuit
        result = breaker.call(lambda: "recovered")
        assert result == "recovered"
        assert breaker.state()["status"] == "closed"
