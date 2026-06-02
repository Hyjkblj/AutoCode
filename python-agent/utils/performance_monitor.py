"""
Performance monitoring and alerting for the Python Agent.

Provides baseline capture, sample recording, percentile calculation, and
degradation detection to satisfy Requirements 12.5 and 12.6.

- PerformanceBaseline: snapshot of expected performance characteristics
- PerformanceSample: a single latency/success observation
- DegradationResult: outcome of a degradation check
- PerformanceMonitor: records samples and evaluates degradation

Default thresholds (relative to baseline):
  - P95 latency  : must not exceed baseline × 1.20  (20 % regression budget)
  - Throughput   : must not fall below baseline × 0.80 (20 % drop budget)
  - Error rate   : must not exceed baseline + 0.01   (1 pp absolute budget)

**Validates: Requirements 12.5, 12.6**
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import List


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PerformanceBaseline:
    """
    Snapshot of expected (healthy) performance characteristics.

    :param p95_latency_ms: 95th-percentile latency in milliseconds.
    :param throughput_rps: Expected requests per second.
    :param error_rate: Expected fraction of failed requests in [0.0, 1.0].
    :param captured_at: Unix timestamp when the baseline was captured.
    """
    p95_latency_ms: float
    throughput_rps: float
    error_rate: float
    captured_at: float = field(default_factory=time.time)


@dataclass
class PerformanceSample:
    """
    A single performance observation.

    :param latency_ms: Round-trip latency in milliseconds (>= 0).
    :param success: Whether the request succeeded.
    :param timestamp: Unix timestamp of the observation.
    """
    latency_ms: float
    success: bool
    timestamp: float = field(default_factory=time.time)


@dataclass
class DegradationResult:
    """
    Result of a degradation check against a baseline.

    :param degraded: True when at least one threshold is violated.
    :param violations: Human-readable descriptions of each violation.
    :param current_metrics: The metrics snapshot used for the comparison.
    """
    degraded: bool
    violations: List[str]
    current_metrics: dict


# ---------------------------------------------------------------------------
# Default threshold multipliers / offsets
# ---------------------------------------------------------------------------

#: P95 latency must not exceed baseline × this factor.
DEFAULT_P95_LATENCY_FACTOR: float = 1.20

#: Throughput must not fall below baseline × this factor.
DEFAULT_THROUGHPUT_FACTOR: float = 0.80

#: Error rate must not exceed baseline + this absolute offset.
DEFAULT_ERROR_RATE_OFFSET: float = 0.01


# ---------------------------------------------------------------------------
# PerformanceMonitor
# ---------------------------------------------------------------------------

class PerformanceMonitor:
    """
    Thread-safe collector of performance samples with degradation detection.

    Usage::

        monitor = PerformanceMonitor()
        monitor.record_sample(latency_ms=42.0, success=True)
        metrics = monitor.get_current_metrics()
        result = monitor.check_degradation(baseline, thresholds)

    **Validates: Requirements 12.5, 12.6**
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._samples: List[PerformanceSample] = []
        self._window_start: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_sample(self, latency_ms: float, success: bool) -> None:
        """
        Record a single performance observation.

        :param latency_ms: Observed latency in milliseconds.  Negative values
            are clamped to 0.
        :param success: Whether the request succeeded.
        """
        sample = PerformanceSample(
            latency_ms=max(0.0, float(latency_ms)),
            success=bool(success),
        )
        with self._lock:
            self._samples.append(sample)

    def get_current_metrics(self) -> dict:
        """
        Compute and return a snapshot of current performance metrics.

        Returns a dict with keys:
          - ``p50_latency_ms``  : median latency
          - ``p95_latency_ms``  : 95th-percentile latency
          - ``p99_latency_ms``  : 99th-percentile latency
          - ``throughput_rps``  : requests per second since the monitor was
            created or last reset
          - ``error_rate``      : fraction of failed requests in [0.0, 1.0]
          - ``sample_count``    : total number of samples recorded

        When no samples have been recorded all latency values are 0.0,
        throughput is 0.0, and error_rate is 0.0.
        """
        with self._lock:
            samples = list(self._samples)
            elapsed = time.monotonic() - self._window_start

        if not samples:
            return {
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "throughput_rps": 0.0,
                "error_rate": 0.0,
                "sample_count": 0,
            }

        latencies = sorted(s.latency_ms for s in samples)
        n = len(latencies)

        p50 = _percentile(latencies, 50)
        p95 = _percentile(latencies, 95)
        p99 = _percentile(latencies, 99)

        failures = sum(1 for s in samples if not s.success)
        error_rate = failures / n

        throughput = n / max(elapsed, 1e-9)

        return {
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "p99_latency_ms": p99,
            "throughput_rps": throughput,
            "error_rate": error_rate,
            "sample_count": n,
        }

    def check_degradation(
        self,
        baseline: PerformanceBaseline,
        thresholds: dict | None = None,
    ) -> DegradationResult:
        """
        Compare current metrics against *baseline* and return a
        :class:`DegradationResult`.

        :param baseline: The healthy-state snapshot to compare against.
        :param thresholds: Optional override dict with keys:
            - ``p95_latency_factor``  (default 1.20)
            - ``throughput_factor``   (default 0.80)
            - ``error_rate_offset``   (default 0.01)

        :returns: :class:`DegradationResult` with ``degraded=True`` when any
            threshold is violated.

        **Validates: Requirements 12.5**
        """
        if thresholds is None:
            thresholds = {}

        p95_factor = float(thresholds.get("p95_latency_factor", DEFAULT_P95_LATENCY_FACTOR))
        tp_factor = float(thresholds.get("throughput_factor", DEFAULT_THROUGHPUT_FACTOR))
        er_offset = float(thresholds.get("error_rate_offset", DEFAULT_ERROR_RATE_OFFSET))

        current = self.get_current_metrics()
        violations: list[str] = []

        # P95 latency check
        p95_limit = baseline.p95_latency_ms * p95_factor
        if current["p95_latency_ms"] > p95_limit:
            violations.append(
                f"P95 latency {current['p95_latency_ms']:.2f} ms exceeds "
                f"threshold {p95_limit:.2f} ms "
                f"(baseline {baseline.p95_latency_ms:.2f} ms × {p95_factor})"
            )

        # Throughput check (only when we have samples to compare)
        if current["sample_count"] > 0:
            tp_limit = baseline.throughput_rps * tp_factor
            if current["throughput_rps"] < tp_limit:
                violations.append(
                    f"Throughput {current['throughput_rps']:.2f} rps below "
                    f"threshold {tp_limit:.2f} rps "
                    f"(baseline {baseline.throughput_rps:.2f} rps × {tp_factor})"
                )

        # Error rate check
        er_limit = baseline.error_rate + er_offset
        if current["error_rate"] > er_limit:
            violations.append(
                f"Error rate {current['error_rate']:.4f} exceeds "
                f"threshold {er_limit:.4f} "
                f"(baseline {baseline.error_rate:.4f} + {er_offset})"
            )

        return DegradationResult(
            degraded=bool(violations),
            violations=violations,
            current_metrics=current,
        )

    def reset(self) -> None:
        """
        Clear all recorded samples and reset the timing window.

        Useful between test runs or after a baseline is re-captured.
        """
        with self._lock:
            self._samples.clear()
            self._window_start = time.monotonic()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _percentile(sorted_values: list[float], pct: float) -> float:
    """
    Compute the *pct*-th percentile of a pre-sorted list using the
    nearest-rank method.

    :param sorted_values: Non-empty list of floats sorted in ascending order.
    :param pct: Percentile in [0, 100].
    :returns: The percentile value.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    # Nearest-rank: index = ceil(pct/100 * n) - 1, clamped to [0, n-1]
    idx = max(0, min(n - 1, int((pct / 100.0) * n + 0.5) - 1))
    return sorted_values[idx]
