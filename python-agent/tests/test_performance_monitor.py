"""
Tests for performance monitoring and alerting.

Task 28.3: Implement performance monitoring and alerting
Validates: Requirements 12.5, 12.6

Covers:
  - Unit tests for record_sample() and get_current_metrics()
  - Unit tests for check_degradation() with various scenarios
  - Unit tests for P95 latency calculation accuracy
  - Property test: for any sequence of samples, p95 >= p50
  - Property test: error_rate is always in [0.0, 1.0]
"""
from __future__ import annotations

import time

import pytest
from hypothesis import given, settings, strategies as st

from utils.performance_monitor import (
    DegradationResult,
    PerformanceBaseline,
    PerformanceMonitor,
    PerformanceSample,
    _percentile,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _monitor() -> PerformanceMonitor:
    """Return a fresh PerformanceMonitor for each test."""
    return PerformanceMonitor()


def _baseline(
    p95_latency_ms: float = 100.0,
    throughput_rps: float = 50.0,
    error_rate: float = 0.01,
) -> PerformanceBaseline:
    return PerformanceBaseline(
        p95_latency_ms=p95_latency_ms,
        throughput_rps=throughput_rps,
        error_rate=error_rate,
    )


# ---------------------------------------------------------------------------
# Unit tests: record_sample and get_current_metrics
# ---------------------------------------------------------------------------

class TestRecordSampleAndGetCurrentMetrics:
    """Unit tests for record_sample() and get_current_metrics()."""

    def test_empty_monitor_returns_zero_metrics(self) -> None:
        m = _monitor()
        metrics = m.get_current_metrics()
        assert metrics["p50_latency_ms"] == 0.0
        assert metrics["p95_latency_ms"] == 0.0
        assert metrics["p99_latency_ms"] == 0.0
        assert metrics["throughput_rps"] == 0.0
        assert metrics["error_rate"] == 0.0
        assert metrics["sample_count"] == 0

    def test_single_successful_sample(self) -> None:
        m = _monitor()
        m.record_sample(latency_ms=50.0, success=True)
        metrics = m.get_current_metrics()
        assert metrics["sample_count"] == 1
        assert metrics["p50_latency_ms"] == 50.0
        assert metrics["p95_latency_ms"] == 50.0
        assert metrics["p99_latency_ms"] == 50.0
        assert metrics["error_rate"] == 0.0

    def test_single_failed_sample(self) -> None:
        m = _monitor()
        m.record_sample(latency_ms=200.0, success=False)
        metrics = m.get_current_metrics()
        assert metrics["sample_count"] == 1
        assert metrics["error_rate"] == 1.0

    def test_all_failures_gives_error_rate_one(self) -> None:
        m = _monitor()
        for _ in range(5):
            m.record_sample(latency_ms=10.0, success=False)
        assert m.get_current_metrics()["error_rate"] == 1.0

    def test_all_successes_gives_error_rate_zero(self) -> None:
        m = _monitor()
        for _ in range(5):
            m.record_sample(latency_ms=10.0, success=True)
        assert m.get_current_metrics()["error_rate"] == 0.0

    def test_mixed_success_failure_error_rate(self) -> None:
        m = _monitor()
        # 3 successes, 1 failure → error_rate = 0.25
        for _ in range(3):
            m.record_sample(latency_ms=10.0, success=True)
        m.record_sample(latency_ms=10.0, success=False)
        metrics = m.get_current_metrics()
        assert metrics["error_rate"] == pytest.approx(0.25)

    def test_negative_latency_clamped_to_zero(self) -> None:
        m = _monitor()
        m.record_sample(latency_ms=-50.0, success=True)
        metrics = m.get_current_metrics()
        assert metrics["p50_latency_ms"] == 0.0

    def test_sample_count_increments(self) -> None:
        m = _monitor()
        for i in range(10):
            m.record_sample(latency_ms=float(i), success=True)
        assert m.get_current_metrics()["sample_count"] == 10

    def test_throughput_is_positive_after_samples(self) -> None:
        m = _monitor()
        for _ in range(5):
            m.record_sample(latency_ms=10.0, success=True)
        assert m.get_current_metrics()["throughput_rps"] > 0.0

    def test_reset_clears_all_samples(self) -> None:
        m = _monitor()
        for _ in range(5):
            m.record_sample(latency_ms=100.0, success=True)
        m.reset()
        metrics = m.get_current_metrics()
        assert metrics["sample_count"] == 0
        assert metrics["p95_latency_ms"] == 0.0
        assert metrics["error_rate"] == 0.0

    def test_metrics_keys_present(self) -> None:
        m = _monitor()
        m.record_sample(latency_ms=10.0, success=True)
        metrics = m.get_current_metrics()
        expected_keys = {
            "p50_latency_ms",
            "p95_latency_ms",
            "p99_latency_ms",
            "throughput_rps",
            "error_rate",
            "sample_count",
        }
        assert expected_keys.issubset(metrics.keys())


# ---------------------------------------------------------------------------
# Unit tests: P95 latency calculation accuracy
# ---------------------------------------------------------------------------

class TestP95LatencyCalculation:
    """Unit tests for P95 latency calculation accuracy."""

    def test_p95_with_100_uniform_samples(self) -> None:
        """With 100 samples [1..100], P95 should be 95."""
        m = _monitor()
        for i in range(1, 101):
            m.record_sample(latency_ms=float(i), success=True)
        metrics = m.get_current_metrics()
        # P95 of [1..100] is 95 (nearest-rank)
        assert metrics["p95_latency_ms"] == pytest.approx(95.0, abs=2.0)

    def test_p95_with_20_samples(self) -> None:
        """With 20 samples [1..20], P95 should be near 19."""
        m = _monitor()
        for i in range(1, 21):
            m.record_sample(latency_ms=float(i), success=True)
        metrics = m.get_current_metrics()
        # P95 of 20 values: index = ceil(0.95*20) - 1 = 19 - 1 = 18 → value 19
        assert metrics["p95_latency_ms"] == pytest.approx(19.0, abs=1.0)

    def test_p95_greater_than_or_equal_to_p50(self) -> None:
        m = _monitor()
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for lat in latencies:
            m.record_sample(latency_ms=float(lat), success=True)
        metrics = m.get_current_metrics()
        assert metrics["p95_latency_ms"] >= metrics["p50_latency_ms"]

    def test_p99_greater_than_or_equal_to_p95(self) -> None:
        m = _monitor()
        for i in range(1, 101):
            m.record_sample(latency_ms=float(i), success=True)
        metrics = m.get_current_metrics()
        assert metrics["p99_latency_ms"] >= metrics["p95_latency_ms"]

    def test_p95_with_identical_samples(self) -> None:
        """All identical latencies → all percentiles equal that value."""
        m = _monitor()
        for _ in range(50):
            m.record_sample(latency_ms=42.0, success=True)
        metrics = m.get_current_metrics()
        assert metrics["p50_latency_ms"] == pytest.approx(42.0)
        assert metrics["p95_latency_ms"] == pytest.approx(42.0)
        assert metrics["p99_latency_ms"] == pytest.approx(42.0)

    def test_percentile_helper_single_value(self) -> None:
        assert _percentile([7.0], 95) == 7.0

    def test_percentile_helper_two_values(self) -> None:
        result = _percentile([1.0, 2.0], 95)
        assert result in (1.0, 2.0)

    def test_percentile_helper_sorted_ascending(self) -> None:
        values = [float(i) for i in range(1, 11)]
        p50 = _percentile(values, 50)
        p95 = _percentile(values, 95)
        assert p95 >= p50


# ---------------------------------------------------------------------------
# Unit tests: check_degradation
# ---------------------------------------------------------------------------

class TestCheckDegradation:
    """Unit tests for check_degradation() with various scenarios."""

    def test_no_degradation_when_metrics_within_thresholds(self) -> None:
        m = _monitor()
        # Record samples well within baseline
        for _ in range(20):
            m.record_sample(latency_ms=80.0, success=True)
        baseline = _baseline(p95_latency_ms=100.0, throughput_rps=1.0, error_rate=0.0)
        result = m.check_degradation(baseline)
        assert isinstance(result, DegradationResult)
        assert result.degraded is False
        assert result.violations == []

    def test_p95_latency_violation_detected(self) -> None:
        m = _monitor()
        # Record high-latency samples: P95 will be ~200 ms
        for _ in range(20):
            m.record_sample(latency_ms=200.0, success=True)
        # Baseline P95 = 100 ms, threshold = 100 × 1.20 = 120 ms → violated
        baseline = _baseline(p95_latency_ms=100.0, throughput_rps=1.0, error_rate=0.0)
        result = m.check_degradation(baseline)
        assert result.degraded is True
        assert any("P95 latency" in v for v in result.violations)

    def test_error_rate_violation_detected(self) -> None:
        m = _monitor()
        # 50% error rate
        for _ in range(5):
            m.record_sample(latency_ms=10.0, success=True)
        for _ in range(5):
            m.record_sample(latency_ms=10.0, success=False)
        # Baseline error_rate = 0.0, threshold = 0.0 + 0.01 = 0.01 → violated
        baseline = _baseline(p95_latency_ms=200.0, throughput_rps=1.0, error_rate=0.0)
        result = m.check_degradation(baseline)
        assert result.degraded is True
        assert any("Error rate" in v for v in result.violations)

    def test_multiple_violations_reported(self) -> None:
        m = _monitor()
        # High latency + high error rate
        for _ in range(10):
            m.record_sample(latency_ms=500.0, success=False)
        baseline = _baseline(p95_latency_ms=100.0, throughput_rps=1.0, error_rate=0.0)
        result = m.check_degradation(baseline)
        assert result.degraded is True
        assert len(result.violations) >= 2

    def test_current_metrics_included_in_result(self) -> None:
        m = _monitor()
        m.record_sample(latency_ms=50.0, success=True)
        baseline = _baseline()
        result = m.check_degradation(baseline)
        assert isinstance(result.current_metrics, dict)
        assert "p95_latency_ms" in result.current_metrics

    def test_custom_thresholds_respected(self) -> None:
        m = _monitor()
        # P95 = 110 ms; with strict threshold (factor=1.05) this should violate
        for _ in range(20):
            m.record_sample(latency_ms=110.0, success=True)
        baseline = _baseline(p95_latency_ms=100.0, throughput_rps=1.0, error_rate=0.0)
        strict_thresholds = {"p95_latency_factor": 1.05}
        result = m.check_degradation(baseline, thresholds=strict_thresholds)
        assert result.degraded is True

    def test_lenient_thresholds_no_violation(self) -> None:
        m = _monitor()
        # P95 = 150 ms; with lenient threshold (factor=2.0) this should pass
        for _ in range(20):
            m.record_sample(latency_ms=150.0, success=True)
        baseline = _baseline(p95_latency_ms=100.0, throughput_rps=1.0, error_rate=0.0)
        lenient_thresholds = {
            "p95_latency_factor": 2.0,
            "throughput_factor": 0.1,
            "error_rate_offset": 0.5,
        }
        result = m.check_degradation(baseline, thresholds=lenient_thresholds)
        assert result.degraded is False

    def test_empty_monitor_no_degradation(self) -> None:
        """An empty monitor has 0 ms P95 and 0 error rate — should not degrade."""
        m = _monitor()
        baseline = _baseline(p95_latency_ms=100.0, throughput_rps=50.0, error_rate=0.0)
        result = m.check_degradation(baseline)
        # P95 = 0 ≤ 120, error_rate = 0 ≤ 0.01 → no degradation
        assert result.degraded is False

    def test_degradation_result_is_dataclass(self) -> None:
        m = _monitor()
        m.record_sample(latency_ms=10.0, success=True)
        result = m.check_degradation(_baseline())
        assert hasattr(result, "degraded")
        assert hasattr(result, "violations")
        assert hasattr(result, "current_metrics")


# ---------------------------------------------------------------------------
# Property test: p95 >= p50 for any sequence of samples
# ---------------------------------------------------------------------------

class TestPropertyP95GeP50:
    """
    Property test: for any sequence of samples, p95 latency >= p50 latency.

    **Validates: Requirements 12.5**
    """

    @given(
        st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
                st.booleans(),
            ),
            min_size=1,
            max_size=200,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_p95_always_gte_p50(self, samples: list[tuple[float, bool]]) -> None:
        """
        For any non-empty sequence of (latency_ms, success) samples,
        p95_latency_ms SHALL always be >= p50_latency_ms.

        **Validates: Requirements 12.5**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)
        metrics = m.get_current_metrics()
        assert metrics["p95_latency_ms"] >= metrics["p50_latency_ms"], (
            f"p95={metrics['p95_latency_ms']} must be >= p50={metrics['p50_latency_ms']}"
        )

    @given(
        st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
                st.booleans(),
            ),
            min_size=1,
            max_size=200,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_p99_always_gte_p95(self, samples: list[tuple[float, bool]]) -> None:
        """
        For any non-empty sequence of samples, p99_latency_ms >= p95_latency_ms.

        **Validates: Requirements 12.5**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)
        metrics = m.get_current_metrics()
        assert metrics["p99_latency_ms"] >= metrics["p95_latency_ms"], (
            f"p99={metrics['p99_latency_ms']} must be >= p95={metrics['p95_latency_ms']}"
        )


# ---------------------------------------------------------------------------
# Property test: error_rate always in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestPropertyErrorRateInRange:
    """
    Property test: error_rate is always in [0.0, 1.0].

    **Validates: Requirements 12.5**
    """

    @given(
        st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
                st.booleans(),
            ),
            min_size=0,
            max_size=200,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_error_rate_always_in_unit_interval(
        self, samples: list[tuple[float, bool]]
    ) -> None:
        """
        For any sequence of (latency_ms, success) samples (including empty),
        error_rate SHALL always be in [0.0, 1.0].

        **Validates: Requirements 12.5**
        """
        m = _monitor()
        for latency, success in samples:
            m.record_sample(latency_ms=latency, success=success)
        metrics = m.get_current_metrics()
        assert 0.0 <= metrics["error_rate"] <= 1.0, (
            f"error_rate={metrics['error_rate']} must be in [0.0, 1.0]"
        )

    @given(
        st.lists(st.booleans(), min_size=1, max_size=500)
    )
    @settings(max_examples=100, deadline=None)
    def test_error_rate_matches_failure_fraction(
        self, successes: list[bool]
    ) -> None:
        """
        For any list of success flags, error_rate SHALL equal
        (number of False values) / len(successes).

        **Validates: Requirements 12.5**
        """
        m = _monitor()
        for s in successes:
            m.record_sample(latency_ms=10.0, success=s)
        metrics = m.get_current_metrics()
        expected = successes.count(False) / len(successes)
        assert metrics["error_rate"] == pytest.approx(expected, abs=1e-9), (
            f"error_rate={metrics['error_rate']} must equal {expected}"
        )
