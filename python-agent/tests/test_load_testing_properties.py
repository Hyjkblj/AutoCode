"""
Property-based tests for load testing configuration and performance validation.

Task 28.4: Write property tests for performance validation
Property 41: Load Testing Configuration
Validates: Requirements 12.2

These tests validate that "THE system SHALL support load testing with configurable
concurrent users and request patterns."

Properties covered:
  41a: LoadTestConfig validates concurrent_users (< 1 raises ValueError, >= 1 succeeds)
  41b: LoadTestConfig validates duration_seconds (< 1 raises ValueError, valid values succeed)
  41c: PerformanceMonitor p95 >= p50 for any non-empty sample sequence
  41d: PerformanceMonitor error_rate in [0.0, 1.0] for any sample sequence
  41e: LoadTestResult throughput_rps is non-negative for any valid result
  41f: LoadTestResult error_rate in [0.0, 1.0] for any valid result
  41g: DegradationResult.degraded is True iff violations is non-empty
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import assume, given, settings, strategies as st

# ---------------------------------------------------------------------------
# Import LoadTestConfig / LoadTestResult from scripts/load-test.py
# The script lives at <repo-root>/scripts/load-test.py and is not a package,
# so we add the scripts directory to sys.path and import via importlib.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("load_test", _SCRIPTS_DIR / "load-test.py")
_load_test_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_load_test_mod)  # type: ignore[union-attr]

LoadTestConfig = _load_test_mod.LoadTestConfig
LoadTestResult = _load_test_mod.LoadTestResult
LoadTestScenario = _load_test_mod.LoadTestScenario

# ---------------------------------------------------------------------------
# Import PerformanceMonitor from utils
# ---------------------------------------------------------------------------

from utils.performance_monitor import (
    DegradationResult,
    PerformanceBaseline,
    PerformanceMonitor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monitor() -> PerformanceMonitor:
    """Return a fresh PerformanceMonitor."""
    return PerformanceMonitor()


def _make_load_test_result(
    total: int,
    successful: int,
    failed: int,
    p50: float,
    p95: float,
    p99: float,
    throughput: float,
    error_rate: float,
    duration: float,
) -> LoadTestResult:
    return LoadTestResult(
        total_requests=total,
        successful_requests=successful,
        failed_requests=failed,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        throughput_rps=throughput,
        error_rate=error_rate,
        duration_seconds=duration,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid concurrent_users: integers >= 1
_valid_users_strategy = st.integers(min_value=1, max_value=1000)

# Invalid concurrent_users: integers < 1
_invalid_users_strategy = st.integers(min_value=-1000, max_value=0)

# Valid duration_seconds: integers >= 2 (must be > ramp_up which is >= 0)
_valid_duration_strategy = st.integers(min_value=2, max_value=3600)

# Invalid duration_seconds: integers < 1
_invalid_duration_strategy = st.integers(min_value=-1000, max_value=0)

# Latency samples: non-negative floats
_latency_strategy = st.floats(
    min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)

# Success flag
_success_strategy = st.booleans()

# Non-empty sample list: list of (latency_ms, success) tuples
_samples_strategy = st.lists(
    st.tuples(_latency_strategy, _success_strategy),
    min_size=1,
    max_size=200,
)

# Any sample list (including empty)
_any_samples_strategy = st.lists(
    st.tuples(_latency_strategy, _success_strategy),
    min_size=0,
    max_size=200,
)

# Valid throughput: non-negative float
_throughput_strategy = st.floats(
    min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)

# Valid error_rate: float in [0.0, 1.0]
_error_rate_strategy = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)

# Valid latency percentile: non-negative float
_latency_pct_strategy = st.floats(
    min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)

# Valid duration for LoadTestResult: positive float
_duration_strategy = st.floats(
    min_value=0.001, max_value=86400.0, allow_nan=False, allow_infinity=False
)

# Scenario strategy
_scenario_strategy = st.sampled_from(list(LoadTestScenario))

# URL strategy: simple valid base URLs
_url_strategy = st.just("http://localhost:8080")


# ---------------------------------------------------------------------------
# Property 41a: LoadTestConfig validates concurrent_users
# ---------------------------------------------------------------------------

class TestProperty41aConcurrentUsersValidation:
    """
    Property 41a: LoadTestConfig validates concurrent_users.

    For any concurrent_users < 1, LoadTestConfig SHALL raise ValueError.
    For any concurrent_users >= 1, LoadTestConfig SHALL be created successfully.

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(_invalid_users_strategy, _valid_duration_strategy, _scenario_strategy)
    @settings(max_examples=50, deadline=None)
    def test_concurrent_users_below_one_raises_value_error(
        self, users: int, duration: int, scenario: LoadTestScenario
    ) -> None:
        """
        For any concurrent_users < 1, LoadTestConfig SHALL raise ValueError.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        # ramp_up must be < duration; use 0 as safe default
        with pytest.raises(ValueError, match="concurrent_users"):
            LoadTestConfig(
                base_url="http://localhost:8080",
                concurrent_users=users,
                duration_seconds=duration,
                ramp_up_seconds=0,
                scenario=scenario,
            )

    @given(_valid_users_strategy, _valid_duration_strategy, _scenario_strategy)
    @settings(max_examples=50, deadline=None)
    def test_concurrent_users_one_or_more_creates_config(
        self, users: int, duration: int, scenario: LoadTestScenario
    ) -> None:
        """
        For any concurrent_users >= 1, LoadTestConfig SHALL be created successfully.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        config = LoadTestConfig(
            base_url="http://localhost:8080",
            concurrent_users=users,
            duration_seconds=duration,
            ramp_up_seconds=0,
            scenario=scenario,
        )
        assert config.concurrent_users == users, (
            f"concurrent_users must be preserved: expected {users}, "
            f"got {config.concurrent_users}"
        )

    def test_concurrent_users_exactly_one_is_valid(self) -> None:
        """Boundary: concurrent_users=1 is the minimum valid value."""
        config = LoadTestConfig(
            base_url="http://localhost:8080",
            concurrent_users=1,
            duration_seconds=10,
            ramp_up_seconds=0,
            scenario=LoadTestScenario.HEALTH_CHECK,
        )
        assert config.concurrent_users == 1

    def test_concurrent_users_zero_raises_value_error(self) -> None:
        """Boundary: concurrent_users=0 must raise ValueError."""
        with pytest.raises(ValueError, match="concurrent_users"):
            LoadTestConfig(
                base_url="http://localhost:8080",
                concurrent_users=0,
                duration_seconds=10,
                ramp_up_seconds=0,
                scenario=LoadTestScenario.HEALTH_CHECK,
            )


# ---------------------------------------------------------------------------
# Property 41b: LoadTestConfig validates duration_seconds
# ---------------------------------------------------------------------------

class TestProperty41bDurationSecondsValidation:
    """
    Property 41b: LoadTestConfig validates duration_seconds.

    For any duration_seconds < 1, LoadTestConfig SHALL raise ValueError.
    For any duration_seconds >= 1 (and > ramp_up), LoadTestConfig SHALL be
    created successfully.

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(_invalid_duration_strategy, _scenario_strategy)
    @settings(max_examples=50, deadline=None)
    def test_duration_below_one_raises_value_error(
        self, duration: int, scenario: LoadTestScenario
    ) -> None:
        """
        For any duration_seconds < 1, LoadTestConfig SHALL raise ValueError.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        with pytest.raises(ValueError, match="duration_seconds"):
            LoadTestConfig(
                base_url="http://localhost:8080",
                concurrent_users=1,
                duration_seconds=duration,
                ramp_up_seconds=0,
                scenario=scenario,
            )

    @given(_valid_duration_strategy, _scenario_strategy)
    @settings(max_examples=50, deadline=None)
    def test_duration_one_or_more_with_zero_ramp_up_creates_config(
        self, duration: int, scenario: LoadTestScenario
    ) -> None:
        """
        For any duration_seconds >= 2 with ramp_up=0, LoadTestConfig SHALL
        be created successfully.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        # duration >= 2 ensures duration > ramp_up=0 (ramp_up < duration required)
        config = LoadTestConfig(
            base_url="http://localhost:8080",
            concurrent_users=1,
            duration_seconds=duration,
            ramp_up_seconds=0,
            scenario=scenario,
        )
        assert config.duration_seconds == duration, (
            f"duration_seconds must be preserved: expected {duration}, "
            f"got {config.duration_seconds}"
        )

    def test_duration_exactly_one_with_zero_ramp_up_is_valid(self) -> None:
        """Boundary: duration_seconds=1 with ramp_up=0 is valid."""
        config = LoadTestConfig(
            base_url="http://localhost:8080",
            concurrent_users=1,
            duration_seconds=1,
            ramp_up_seconds=0,
            scenario=LoadTestScenario.HEALTH_CHECK,
        )
        assert config.duration_seconds == 1

    def test_duration_zero_raises_value_error(self) -> None:
        """Boundary: duration_seconds=0 must raise ValueError."""
        with pytest.raises(ValueError, match="duration_seconds"):
            LoadTestConfig(
                base_url="http://localhost:8080",
                concurrent_users=1,
                duration_seconds=0,
                ramp_up_seconds=0,
                scenario=LoadTestScenario.HEALTH_CHECK,
            )

    @given(
        st.integers(min_value=2, max_value=3600),
        _scenario_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_ramp_up_equal_to_duration_raises_value_error(
        self, duration: int, scenario: LoadTestScenario
    ) -> None:
        """
        For any duration, ramp_up_seconds == duration_seconds SHALL raise ValueError
        (ramp_up must be strictly less than duration).

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        with pytest.raises(ValueError, match="ramp_up_seconds"):
            LoadTestConfig(
                base_url="http://localhost:8080",
                concurrent_users=1,
                duration_seconds=duration,
                ramp_up_seconds=duration,  # equal → invalid
                scenario=scenario,
            )


# ---------------------------------------------------------------------------
# Property 41c: PerformanceMonitor p95 >= p50 for any sample sequence
# ---------------------------------------------------------------------------

class TestProperty41cP95GeP50:
    """
    Property 41c: PerformanceMonitor p95 >= p50 for any non-empty sample sequence.

    For any non-empty sequence of latency samples, p95_latency_ms SHALL always
    be >= p50_latency_ms.

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(_samples_strategy)
    @settings(max_examples=100, deadline=None)
    def test_p95_always_gte_p50_for_any_samples(
        self, samples: list[tuple[float, bool]]
    ) -> None:
        """
        For any non-empty sequence of (latency_ms, success) samples,
        p95_latency_ms SHALL always be >= p50_latency_ms.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)
        metrics = m.get_current_metrics()
        assert metrics["p95_latency_ms"] >= metrics["p50_latency_ms"], (
            f"p95={metrics['p95_latency_ms']} must be >= p50={metrics['p50_latency_ms']}"
        )

    @given(_samples_strategy)
    @settings(max_examples=100, deadline=None)
    def test_p99_always_gte_p95_for_any_samples(
        self, samples: list[tuple[float, bool]]
    ) -> None:
        """
        For any non-empty sequence of samples, p99_latency_ms >= p95_latency_ms.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)
        metrics = m.get_current_metrics()
        assert metrics["p99_latency_ms"] >= metrics["p95_latency_ms"], (
            f"p99={metrics['p99_latency_ms']} must be >= p95={metrics['p95_latency_ms']}"
        )


# ---------------------------------------------------------------------------
# Property 41d: PerformanceMonitor error_rate in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestProperty41dErrorRateInRange:
    """
    Property 41d: PerformanceMonitor error_rate in [0.0, 1.0].

    For any sequence of success/failure samples, error_rate SHALL always be
    in [0.0, 1.0].

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(_any_samples_strategy)
    @settings(max_examples=100, deadline=None)
    def test_error_rate_always_in_unit_interval(
        self, samples: list[tuple[float, bool]]
    ) -> None:
        """
        For any sequence of (latency_ms, success) samples (including empty),
        error_rate SHALL always be in [0.0, 1.0].

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)
        metrics = m.get_current_metrics()
        assert 0.0 <= metrics["error_rate"] <= 1.0, (
            f"error_rate={metrics['error_rate']} must be in [0.0, 1.0]"
        )

    @given(st.lists(st.booleans(), min_size=1, max_size=500))
    @settings(max_examples=100, deadline=None)
    def test_error_rate_matches_failure_fraction(
        self, successes: list[bool]
    ) -> None:
        """
        For any list of success flags, error_rate SHALL equal
        (number of False values) / len(successes).

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        m = _monitor()
        for s in successes:
            m.record_sample(latency_ms=10.0, success=s)
        metrics = m.get_current_metrics()
        expected = successes.count(False) / len(successes)
        assert metrics["error_rate"] == pytest.approx(expected, abs=1e-9), (
            f"error_rate={metrics['error_rate']} must equal {expected}"
        )


# ---------------------------------------------------------------------------
# Property 41e: LoadTestResult throughput_rps is non-negative
# ---------------------------------------------------------------------------

class TestProperty41eThroughputNonNegative:
    """
    Property 41e: LoadTestResult throughput_rps is non-negative.

    For any valid LoadTestResult, throughput_rps SHALL be >= 0.

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(
        st.integers(min_value=0, max_value=100_000),
        _error_rate_strategy,
        _latency_pct_strategy,
        _throughput_strategy,
        _duration_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_throughput_rps_always_non_negative(
        self,
        total: int,
        error_rate: float,
        latency: float,
        throughput: float,
        duration: float,
    ) -> None:
        """
        For any valid LoadTestResult, throughput_rps SHALL be >= 0.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        failed = int(total * error_rate)
        successful = total - failed

        result = _make_load_test_result(
            total=total,
            successful=successful,
            failed=failed,
            p50=latency,
            p95=latency,
            p99=latency,
            throughput=throughput,
            error_rate=error_rate,
            duration=duration,
        )
        assert result.throughput_rps >= 0.0, (
            f"throughput_rps={result.throughput_rps} must be >= 0"
        )

    def test_zero_requests_gives_zero_throughput(self) -> None:
        """A result with zero requests must have zero throughput."""
        result = _make_load_test_result(
            total=0,
            successful=0,
            failed=0,
            p50=0.0,
            p95=0.0,
            p99=0.0,
            throughput=0.0,
            error_rate=0.0,
            duration=1.0,
        )
        assert result.throughput_rps == 0.0

    def test_positive_requests_can_have_positive_throughput(self) -> None:
        """A result with requests and positive duration can have positive throughput."""
        result = _make_load_test_result(
            total=100,
            successful=100,
            failed=0,
            p50=10.0,
            p95=20.0,
            p99=30.0,
            throughput=10.0,
            error_rate=0.0,
            duration=10.0,
        )
        assert result.throughput_rps >= 0.0


# ---------------------------------------------------------------------------
# Property 41f: LoadTestResult error_rate in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestProperty41fLoadTestResultErrorRateInRange:
    """
    Property 41f: LoadTestResult error_rate in [0.0, 1.0].

    For any valid LoadTestResult, error_rate SHALL be in [0.0, 1.0].

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(
        st.integers(min_value=0, max_value=100_000),
        _error_rate_strategy,
        _latency_pct_strategy,
        _throughput_strategy,
        _duration_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_error_rate_always_in_unit_interval(
        self,
        total: int,
        error_rate: float,
        latency: float,
        throughput: float,
        duration: float,
    ) -> None:
        """
        For any valid LoadTestResult, error_rate SHALL be in [0.0, 1.0].

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        failed = int(total * error_rate)
        successful = total - failed

        result = _make_load_test_result(
            total=total,
            successful=successful,
            failed=failed,
            p50=latency,
            p95=latency,
            p99=latency,
            throughput=throughput,
            error_rate=error_rate,
            duration=duration,
        )
        assert 0.0 <= result.error_rate <= 1.0, (
            f"error_rate={result.error_rate} must be in [0.0, 1.0]"
        )

    def test_all_successful_gives_zero_error_rate(self) -> None:
        """A result with all successful requests must have error_rate=0.0."""
        result = _make_load_test_result(
            total=100,
            successful=100,
            failed=0,
            p50=10.0,
            p95=20.0,
            p99=30.0,
            throughput=10.0,
            error_rate=0.0,
            duration=10.0,
        )
        assert result.error_rate == 0.0

    def test_all_failed_gives_one_error_rate(self) -> None:
        """A result with all failed requests must have error_rate=1.0."""
        result = _make_load_test_result(
            total=100,
            successful=0,
            failed=100,
            p50=10.0,
            p95=20.0,
            p99=30.0,
            throughput=10.0,
            error_rate=1.0,
            duration=10.0,
        )
        assert result.error_rate == 1.0


# ---------------------------------------------------------------------------
# Property 41g: DegradationResult.degraded is True iff violations is non-empty
# ---------------------------------------------------------------------------

class TestProperty41gDegradedIffViolationsNonEmpty:
    """
    Property 41g: DegradationResult.degraded is True iff violations is non-empty.

    For any check_degradation result, degraded SHALL equal (len(violations) > 0).

    **Property 41: Load Testing Configuration**
    **Validates: Requirements 12.2**
    """

    @given(_any_samples_strategy)
    @settings(max_examples=100, deadline=None)
    def test_degraded_iff_violations_non_empty(
        self, samples: list[tuple[float, bool]]
    ) -> None:
        """
        For any sample sequence, DegradationResult.degraded SHALL be True
        if and only if violations is non-empty.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)

        # Use a baseline that may or may not be violated
        baseline = PerformanceBaseline(
            p95_latency_ms=100.0,
            throughput_rps=50.0,
            error_rate=0.01,
        )
        result = m.check_degradation(baseline)

        assert result.degraded == (len(result.violations) > 0), (
            f"degraded={result.degraded} must equal "
            f"(len(violations) > 0) where violations={result.violations}"
        )

    @given(
        _any_samples_strategy,
        st.floats(min_value=0.001, max_value=10_000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.001, max_value=10_000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, deadline=None)
    def test_degraded_iff_violations_non_empty_varied_baselines(
        self,
        samples: list[tuple[float, bool]],
        baseline_p95: float,
        baseline_throughput: float,
        baseline_error_rate: float,
    ) -> None:
        """
        For any sample sequence and any baseline values, DegradationResult.degraded
        SHALL be True if and only if violations is non-empty.

        **Property 41: Load Testing Configuration**
        **Validates: Requirements 12.2**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)

        baseline = PerformanceBaseline(
            p95_latency_ms=baseline_p95,
            throughput_rps=baseline_throughput,
            error_rate=baseline_error_rate,
        )
        result = m.check_degradation(baseline)

        assert result.degraded == (len(result.violations) > 0), (
            f"degraded={result.degraded} must equal "
            f"(len(violations) > 0) where violations={result.violations}"
        )

    def test_no_violations_means_not_degraded(self) -> None:
        """When no thresholds are violated, degraded must be False."""
        m = _monitor()
        # Record samples well within baseline
        for _ in range(20):
            m.record_sample(latency_ms=50.0, success=True)
        baseline = PerformanceBaseline(
            p95_latency_ms=200.0,
            throughput_rps=0.1,
            error_rate=0.5,
        )
        result = m.check_degradation(baseline)
        assert result.degraded is False
        assert result.violations == []
        assert result.degraded == (len(result.violations) > 0)

    def test_p95_violation_means_degraded(self) -> None:
        """When P95 threshold is violated, degraded must be True."""
        m = _monitor()
        for _ in range(20):
            m.record_sample(latency_ms=500.0, success=True)
        baseline = PerformanceBaseline(
            p95_latency_ms=100.0,
            throughput_rps=0.1,
            error_rate=0.5,
        )
        result = m.check_degradation(baseline)
        assert result.degraded is True
        assert len(result.violations) > 0
        assert result.degraded == (len(result.violations) > 0)

    def test_error_rate_violation_means_degraded(self) -> None:
        """When error rate threshold is violated, degraded must be True."""
        m = _monitor()
        for _ in range(10):
            m.record_sample(latency_ms=10.0, success=False)
        baseline = PerformanceBaseline(
            p95_latency_ms=10_000.0,
            throughput_rps=0.001,
            error_rate=0.0,
        )
        result = m.check_degradation(baseline)
        assert result.degraded is True
        assert len(result.violations) > 0
        assert result.degraded == (len(result.violations) > 0)
