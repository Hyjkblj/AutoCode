#!/usr/bin/env python3
"""
AutoCode Backend Upgrade 2.0 - Load Testing Framework

Implements configurable load testing with concurrent users, realistic test scenarios,
and performance baseline measurement and comparison.

Requirements:
  12.1 - THE system SHALL establish baseline metrics for P95 latency, throughput, and error rates
  12.2 - THE system SHALL support load testing with configurable concurrent users and request patterns

Usage:
  python scripts/load-test.py --url http://localhost:8080 --users 10 --duration 60 --scenario task_creation
  python scripts/load-test.py --url http://localhost:8080 --users 5 --duration 30 --scenario health_check --save-baseline baselines/health.json
  python scripts/load-test.py --url http://localhost:8080 --users 10 --duration 60 --compare-baseline baselines/health.json
"""

import argparse
import asyncio
import json
import logging
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp is required. Install with: pip install aiohttp")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class LoadTestScenario(str, Enum):
    """Available load test scenarios."""
    TASK_CREATION = "task_creation"
    TASK_POLLING = "task_polling"
    HEALTH_CHECK = "health_check"
    MIXED = "mixed"


@dataclass
class LoadTestConfig:
    """Configuration for a load test run."""
    base_url: str
    concurrent_users: int
    duration_seconds: int
    ramp_up_seconds: int
    scenario: LoadTestScenario

    def __post_init__(self):
        if self.concurrent_users < 1:
            raise ValueError("concurrent_users must be at least 1")
        if self.duration_seconds < 1:
            raise ValueError("duration_seconds must be at least 1")
        if self.ramp_up_seconds < 0:
            raise ValueError("ramp_up_seconds must be non-negative")
        if self.ramp_up_seconds >= self.duration_seconds:
            raise ValueError("ramp_up_seconds must be less than duration_seconds")
        # Normalise base_url: strip trailing slash
        self.base_url = self.base_url.rstrip("/")


@dataclass
class LoadTestResult:
    """Aggregated results from a load test run."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    error_rate: float          # 0.0 – 1.0
    duration_seconds: float

    def summary(self) -> str:
        return (
            f"Requests: {self.total_requests} total, "
            f"{self.successful_requests} ok, "
            f"{self.failed_requests} failed | "
            f"Latency p50={self.p50_latency_ms:.1f}ms "
            f"p95={self.p95_latency_ms:.1f}ms "
            f"p99={self.p99_latency_ms:.1f}ms | "
            f"Throughput={self.throughput_rps:.2f} rps | "
            f"Error rate={self.error_rate * 100:.2f}%"
        )


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------

def _percentile(sorted_values: List[float], pct: float) -> float:
    """Return the *pct*-th percentile from a pre-sorted list (0–100)."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct / 100.0
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


# ---------------------------------------------------------------------------
# Per-scenario request functions
# ---------------------------------------------------------------------------

async def _request_health_check(
    session: aiohttp.ClientSession,
    base_url: str,
) -> Tuple[bool, float]:
    """Single health-check request. Returns (success, latency_ms)."""
    url = f"{base_url}/healthz"
    t0 = time.monotonic()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            latency_ms = (time.monotonic() - t0) * 1000
            return resp.status < 500, latency_ms
    except Exception:
        latency_ms = (time.monotonic() - t0) * 1000
        return False, latency_ms


async def _request_task_creation(
    session: aiohttp.ClientSession,
    base_url: str,
) -> Tuple[bool, float]:
    """Single task-creation request. Returns (success, latency_ms)."""
    url = f"{base_url}/api/v1/tasks"
    payload = {
        "projectId": "load-test-proj",
        "assistant": "codex",
        "agentProfile": "coder",
        "prompt": f"Load test task {uuid.uuid4().hex[:8]}",
    }
    t0 = time.monotonic()
    try:
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            latency_ms = (time.monotonic() - t0) * 1000
            # 200/201 = success; 4xx client errors still count as "received"
            return resp.status < 500, latency_ms
    except Exception:
        latency_ms = (time.monotonic() - t0) * 1000
        return False, latency_ms


async def _request_task_polling(
    session: aiohttp.ClientSession,
    base_url: str,
) -> Tuple[bool, float]:
    """Single task-polling request (GET /api/v1/tasks). Returns (success, latency_ms)."""
    url = f"{base_url}/api/v1/tasks"
    t0 = time.monotonic()
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            latency_ms = (time.monotonic() - t0) * 1000
            return resp.status < 500, latency_ms
    except Exception:
        latency_ms = (time.monotonic() - t0) * 1000
        return False, latency_ms


# ---------------------------------------------------------------------------
# Virtual user coroutine
# ---------------------------------------------------------------------------

async def _virtual_user(
    user_id: int,
    config: LoadTestConfig,
    start_event: asyncio.Event,
    stop_event: asyncio.Event,
    results: List[Tuple[bool, float]],
) -> None:
    """Simulate a single virtual user sending requests until stop_event is set."""
    # Ramp-up: stagger user start times
    if config.ramp_up_seconds > 0 and config.concurrent_users > 1:
        delay = (config.ramp_up_seconds / config.concurrent_users) * user_id
        await asyncio.sleep(delay)

    await start_event.wait()

    connector = aiohttp.TCPConnector(limit=1, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        while not stop_event.is_set():
            scenario = config.scenario

            # For MIXED, rotate through the three concrete scenarios
            if scenario == LoadTestScenario.MIXED:
                idx = len(results) % 3
                scenario = [
                    LoadTestScenario.HEALTH_CHECK,
                    LoadTestScenario.TASK_CREATION,
                    LoadTestScenario.TASK_POLLING,
                ][idx]

            if scenario == LoadTestScenario.HEALTH_CHECK:
                ok, latency = await _request_health_check(session, config.base_url)
            elif scenario == LoadTestScenario.TASK_CREATION:
                ok, latency = await _request_task_creation(session, config.base_url)
            elif scenario == LoadTestScenario.TASK_POLLING:
                ok, latency = await _request_task_polling(session, config.base_url)
            else:
                ok, latency = await _request_health_check(session, config.base_url)

            results.append((ok, latency))

            # Small yield to avoid tight-loop starvation
            await asyncio.sleep(0)


# ---------------------------------------------------------------------------
# LoadTester
# ---------------------------------------------------------------------------

class LoadTester:
    """
    Orchestrates load tests, collects metrics, and manages baselines.

    Example
    -------
    config = LoadTestConfig(
        base_url="http://localhost:8080",
        concurrent_users=10,
        duration_seconds=60,
        ramp_up_seconds=5,
        scenario=LoadTestScenario.HEALTH_CHECK,
    )
    tester = LoadTester()
    result = tester.run(config)
    print(result.summary())
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, config: LoadTestConfig) -> LoadTestResult:
        """
        Execute the load test described by *config* and return aggregated metrics.

        Runs synchronously (blocks until the test completes).
        """
        return asyncio.run(self._run_async(config))

    def compare_with_baseline(
        self,
        result: LoadTestResult,
        baseline_file: str,
    ) -> Dict[str, Dict]:
        """
        Compare *result* against a previously saved baseline.

        Returns a dict keyed by metric name, each value being::

            {
                "baseline": <float>,
                "actual":   <float>,
                "passed":   <bool>,
                "delta_pct": <float>,   # positive = worse
            }

        Thresholds (configurable via class attributes):
          - p95_latency_ms  : actual ≤ baseline × 1.20  (20 % regression allowed)
          - p99_latency_ms  : actual ≤ baseline × 1.20
          - throughput_rps  : actual ≥ baseline × 0.80  (20 % drop allowed)
          - error_rate      : actual ≤ baseline + 0.01  (1 pp absolute tolerance)
        """
        with open(baseline_file, "r", encoding="utf-8") as fh:
            baseline_data = json.load(fh)

        baseline = LoadTestResult(**baseline_data)

        comparison: Dict[str, Dict] = {}

        def _cmp(name: str, actual: float, base: float, higher_is_better: bool) -> None:
            if higher_is_better:
                passed = actual >= base * 0.80
                delta_pct = (base - actual) / base * 100 if base else 0.0
            else:
                passed = actual <= base * 1.20
                delta_pct = (actual - base) / base * 100 if base else 0.0
            comparison[name] = {
                "baseline": base,
                "actual": actual,
                "passed": passed,
                "delta_pct": round(delta_pct, 2),
            }

        _cmp("p95_latency_ms", result.p95_latency_ms, baseline.p95_latency_ms, higher_is_better=False)
        _cmp("p99_latency_ms", result.p99_latency_ms, baseline.p99_latency_ms, higher_is_better=False)
        _cmp("throughput_rps", result.throughput_rps, baseline.throughput_rps, higher_is_better=True)

        # Error rate: absolute tolerance of 1 percentage point
        err_passed = result.error_rate <= baseline.error_rate + 0.01
        comparison["error_rate"] = {
            "baseline": baseline.error_rate,
            "actual": result.error_rate,
            "passed": err_passed,
            "delta_pct": round((result.error_rate - baseline.error_rate) * 100, 2),
        }

        return comparison

    def save_baseline(self, result: LoadTestResult, baseline_file: str) -> None:
        """
        Persist *result* as a JSON baseline file.

        Creates parent directories if they do not exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(baseline_file)), exist_ok=True)
        with open(baseline_file, "w", encoding="utf-8") as fh:
            json.dump(asdict(result), fh, indent=2)
        logger.info("Baseline saved to %s", baseline_file)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_async(self, config: LoadTestConfig) -> LoadTestResult:
        logger.info(
            "Starting load test: scenario=%s users=%d duration=%ds ramp_up=%ds url=%s",
            config.scenario.value,
            config.concurrent_users,
            config.duration_seconds,
            config.ramp_up_seconds,
            config.base_url,
        )

        # Shared result list (appended by all virtual users)
        raw_results: List[Tuple[bool, float]] = []

        start_event = asyncio.Event()
        stop_event = asyncio.Event()

        # Spawn virtual users
        tasks = [
            asyncio.create_task(
                _virtual_user(i, config, start_event, stop_event, raw_results)
            )
            for i in range(config.concurrent_users)
        ]

        wall_start = time.monotonic()
        start_event.set()  # release all users

        # Run for the configured duration
        await asyncio.sleep(config.duration_seconds)
        stop_event.set()

        # Wait for all users to finish their current request
        await asyncio.gather(*tasks, return_exceptions=True)
        wall_duration = time.monotonic() - wall_start

        return self._aggregate(raw_results, wall_duration)

    @staticmethod
    def _aggregate(
        raw: List[Tuple[bool, float]],
        wall_duration: float,
    ) -> LoadTestResult:
        total = len(raw)
        if total == 0:
            return LoadTestResult(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                throughput_rps=0.0,
                error_rate=0.0,
                duration_seconds=wall_duration,
            )

        successes = sum(1 for ok, _ in raw if ok)
        failures = total - successes
        latencies = sorted(lat for _, lat in raw)

        return LoadTestResult(
            total_requests=total,
            successful_requests=successes,
            failed_requests=failures,
            p50_latency_ms=round(_percentile(latencies, 50), 2),
            p95_latency_ms=round(_percentile(latencies, 95), 2),
            p99_latency_ms=round(_percentile(latencies, 99), 2),
            throughput_rps=round(total / wall_duration, 2) if wall_duration > 0 else 0.0,
            error_rate=round(failures / total, 6),
            duration_seconds=round(wall_duration, 3),
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AutoCode load testing framework (Requirements 12.1, 12.2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic health-check load test
  python scripts/load-test.py --url http://localhost:8080 --users 10 --duration 30

  # Task creation scenario, save baseline
  python scripts/load-test.py --url http://localhost:8080 --users 20 --duration 60 \\
      --scenario task_creation --save-baseline scripts/baselines/task_creation.json

  # Compare against saved baseline
  python scripts/load-test.py --url http://localhost:8080 --users 20 --duration 60 \\
      --scenario task_creation --compare-baseline scripts/baselines/task_creation.json
""",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="Base URL of the system under test (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Number of concurrent virtual users (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--ramp-up",
        type=int,
        default=5,
        help="Ramp-up period in seconds (default: 5)",
    )
    parser.add_argument(
        "--scenario",
        choices=[s.value for s in LoadTestScenario],
        default=LoadTestScenario.HEALTH_CHECK.value,
        help="Test scenario to run (default: health_check)",
    )
    parser.add_argument(
        "--save-baseline",
        metavar="FILE",
        help="Save results as a JSON baseline to FILE",
    )
    parser.add_argument(
        "--compare-baseline",
        metavar="FILE",
        help="Compare results against a previously saved baseline FILE",
    )
    parser.add_argument(
        "--output-json",
        metavar="FILE",
        help="Write full result JSON to FILE",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate ramp-up < duration
    if args.ramp_up >= args.duration:
        parser.error("--ramp-up must be less than --duration")

    config = LoadTestConfig(
        base_url=args.url,
        concurrent_users=args.users,
        duration_seconds=args.duration,
        ramp_up_seconds=args.ramp_up,
        scenario=LoadTestScenario(args.scenario),
    )

    tester = LoadTester()

    logger.info("=" * 60)
    logger.info("AutoCode Load Test Framework")
    logger.info("=" * 60)

    result = tester.run(config)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("LOAD TEST RESULTS")
    logger.info("=" * 60)
    logger.info("  Total requests   : %d", result.total_requests)
    logger.info("  Successful       : %d", result.successful_requests)
    logger.info("  Failed           : %d", result.failed_requests)
    logger.info("  Error rate       : %.2f%%", result.error_rate * 100)
    logger.info("  Throughput       : %.2f req/s", result.throughput_rps)
    logger.info("  Latency p50      : %.1f ms", result.p50_latency_ms)
    logger.info("  Latency p95      : %.1f ms", result.p95_latency_ms)
    logger.info("  Latency p99      : %.1f ms", result.p99_latency_ms)
    logger.info("  Duration         : %.1f s", result.duration_seconds)

    # Optionally write JSON output
    if args.output_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_json)), exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as fh:
            json.dump(asdict(result), fh, indent=2)
        logger.info("Results written to %s", args.output_json)

    # Save baseline
    if args.save_baseline:
        tester.save_baseline(result, args.save_baseline)

    # Compare with baseline
    exit_code = 0
    if args.compare_baseline:
        if not os.path.exists(args.compare_baseline):
            logger.error("Baseline file not found: %s", args.compare_baseline)
            return 1

        comparison = tester.compare_with_baseline(result, args.compare_baseline)

        logger.info("\n" + "=" * 60)
        logger.info("BASELINE COMPARISON")
        logger.info("=" * 60)

        all_passed = True
        for metric, info in comparison.items():
            status = "PASS" if info["passed"] else "FAIL"
            direction = "↑" if info["delta_pct"] > 0 else "↓"
            logger.info(
                "  %-20s %s | baseline=%-10.3f actual=%-10.3f delta=%+.1f%% %s",
                metric,
                status,
                info["baseline"],
                info["actual"],
                info["delta_pct"],
                direction,
            )
            if not info["passed"]:
                all_passed = False

        if all_passed:
            logger.info("\n✓ All metrics within acceptable thresholds")
        else:
            logger.error("\n✗ One or more metrics exceeded acceptable thresholds")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
