"""
Engine comparison framework for validating output consistency between
the legacy orchestration engine and the LangGraph engine.

Provides :class:`EngineComparisonFramework` which runs both engines for
a given task and computes consistency metrics.  Discrepancies are logged
for investigation.

Also provides :class:`ComparisonMetricsTracker` which accumulates metrics
over multiple comparisons and supports automated rollback decisions.

**Validates: Requirements 8.4, 8.7**
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from workflows.analyze_workflow import AnalyzeWorkflow
from workflows.code_change_workflow import CodeChangeWorkflow
from workflows.test_workflow import TestWorkflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result and metrics data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EngineResult:
    """
    Holds the output from a single engine execution.

    Attributes
    ----------
    engine:
        Engine identifier (``"legacy"`` or ``"langgraph"``).
    success:
        Whether the engine completed without error.
    payload:
        The terminal payload / result dict produced by the engine.
    latency_seconds:
        Wall-clock time taken by the engine execution.
    error:
        Error message if the engine failed, otherwise ``None``.
    """

    engine: str
    success: bool
    payload: dict[str, Any]
    latency_seconds: float
    error: str | None = None


@dataclass
class ComparisonResult:
    """
    Result of comparing a legacy result against a LangGraph result for a
    single operation.

    Attributes
    ----------
    consistent:
        True when both results agree on success/failure and key outputs match.
    consistency_score:
        Score in [0.0, 1.0].  1.0 means fully consistent; 0.0 means
        completely different.  Score is 1.0 when both succeed or both fail;
        partial credit is given for overlapping keys when one succeeds and
        the other fails.
    discrepancies:
        Human-readable list of differences found between the two results.
    """

    consistent: bool
    consistency_score: float
    discrepancies: list


@dataclass
class ComparisonMetrics:
    """
    Metrics computed from comparing legacy and LangGraph engine outputs.

    Attributes
    ----------
    intent:
        The task intent that was compared (``"analyze"`` or ``"test"``).
    legacy_success:
        Whether the legacy engine succeeded.
    langgraph_success:
        Whether the LangGraph engine succeeded.
    success_rate:
        Fraction of engines that succeeded (0.0 – 1.0).
    output_consistency_score:
        Score in [0.0, 1.0] measuring how similar the two outputs are.
        1.0 means fully consistent; 0.0 means completely different.
    latency_comparison:
        Dict with ``legacy_seconds``, ``langgraph_seconds``, and
        ``speedup`` (legacy / langgraph, >1 means LangGraph is faster).
    discrepancies:
        List of human-readable discrepancy descriptions.
    """

    intent: str
    legacy_success: bool
    langgraph_success: bool
    success_rate: float
    output_consistency_score: float
    latency_comparison: dict[str, float] = field(default_factory=dict)
    discrepancies: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Key fields used for consistency comparison per intent
# ---------------------------------------------------------------------------

_ANALYZE_CONSISTENCY_KEYS: tuple[str, ...] = (
    "result",
    "intent",
    "planName",
    "executionPath",
)

_TEST_CONSISTENCY_KEYS: tuple[str, ...] = (
    "result",
    "intent",
    "planName",
    "status",
    "executionPath",
)

_CODE_CHANGE_CONSISTENCY_KEYS: tuple[str, ...] = (
    "result",
    "intent",
    "success",
    "planName",
    "change_type",
    "executionPath",
)


# ---------------------------------------------------------------------------
# EngineComparisonFramework
# ---------------------------------------------------------------------------

class EngineComparisonFramework:
    """
    Compares legacy and LangGraph engine outputs for analyze, test, and
    code_change tasks.

    The framework runs both engines for a given task, collects their
    outputs, and computes consistency metrics.  Any discrepancies are
    logged at WARNING level for investigation.

    Parameters
    ----------
    analyze_workflow:
        Optional :class:`~workflows.analyze_workflow.AnalyzeWorkflow`
        instance.  A default instance is created when *None*.
    test_workflow:
        Optional :class:`~workflows.test_workflow.TestWorkflow` instance.
        A default instance is created when *None*.
    code_change_workflow:
        Optional :class:`~workflows.code_change_workflow.CodeChangeWorkflow`
        instance.  A default instance is created when *None*.
    legacy_analyze_handler:
        Optional callable that accepts a task dict and returns a legacy
        analyze result dict.  When *None* a built-in stub is used.
    legacy_test_handler:
        Optional callable that accepts a task dict and returns a legacy
        test result dict.  When *None* a built-in stub is used.
    legacy_code_change_handler:
        Optional callable that accepts a task dict and returns a legacy
        code_change result dict.  When *None* a built-in stub is used.

    **Validates: Requirements 8.4, 8.7**
    """

    def __init__(
        self,
        *,
        analyze_workflow: AnalyzeWorkflow | None = None,
        test_workflow: TestWorkflow | None = None,
        code_change_workflow: CodeChangeWorkflow | None = None,
        legacy_analyze_handler: Any | None = None,
        legacy_test_handler: Any | None = None,
        legacy_code_change_handler: Any | None = None,
    ) -> None:
        self._analyze_workflow = analyze_workflow
        self._test_workflow = test_workflow
        self._code_change_workflow = code_change_workflow
        self._legacy_analyze_handler = legacy_analyze_handler
        self._legacy_test_handler = legacy_test_handler
        self._legacy_code_change_handler = legacy_code_change_handler

    # ------------------------------------------------------------------
    # Lazy-initialised workflow accessors
    # ------------------------------------------------------------------

    @property
    def analyze_workflow(self) -> AnalyzeWorkflow:
        """Return the :class:`AnalyzeWorkflow`, creating one on first access."""
        if self._analyze_workflow is None:
            self._analyze_workflow = AnalyzeWorkflow()
        return self._analyze_workflow

    @property
    def test_workflow(self) -> TestWorkflow:
        """Return the :class:`TestWorkflow`, creating one on first access."""
        if self._test_workflow is None:
            self._test_workflow = TestWorkflow()
        return self._test_workflow

    @property
    def code_change_workflow(self) -> CodeChangeWorkflow:
        """Return the :class:`CodeChangeWorkflow`, creating one on first access."""
        if self._code_change_workflow is None:
            self._code_change_workflow = CodeChangeWorkflow()
        return self._code_change_workflow

    # ------------------------------------------------------------------
    # Public comparison methods
    # ------------------------------------------------------------------

    def compare(
        self,
        operation: str,
        legacy_result: dict[str, Any],
        langgraph_result: dict[str, Any],
    ) -> ComparisonResult:
        """
        Compare a legacy result against a LangGraph result for a given operation.

        This is the primary comparison entry point.  It accepts pre-computed
        result dicts (rather than running the engines) and returns a
        :class:`ComparisonResult` with a consistency score and any
        discrepancies found.

        Scoring rules
        -------------
        - If both results indicate success (non-empty, no ``"error"`` key) or
          both indicate failure, the base score is 1.0.
        - If one succeeds and the other fails, the base score is 0.5 minus a
          penalty proportional to the number of mismatched keys.
        - The final score is always clamped to [0.0, 1.0].
        - Discrepancies are logged at WARNING level.

        Parameters
        ----------
        operation:
            Operation name (e.g. ``"analyze"`` or ``"test"``).
        legacy_result:
            Result dict produced by the legacy engine.
        langgraph_result:
            Result dict produced by the LangGraph engine.

        Returns
        -------
        ComparisonResult
            Comparison result with consistency score and discrepancies.

        **Validates: Requirements 8.4**
        """
        discrepancies: list[str] = []

        legacy_success = bool(legacy_result) and "error" not in legacy_result
        langgraph_success = bool(langgraph_result) and "error" not in langgraph_result

        if legacy_success == langgraph_success:
            # Both agree on success/failure – start with perfect score
            base_score = 1.0
        else:
            # Disagreement on success/failure
            discrepancies.append(
                f"Success mismatch: legacy_success={legacy_success} "
                f"langgraph_success={langgraph_success}"
            )
            base_score = 0.5

        # Compare overlapping keys
        all_keys = set(legacy_result.keys()) | set(langgraph_result.keys())
        if all_keys:
            key_matches = sum(
                1
                for k in all_keys
                if legacy_result.get(k) == langgraph_result.get(k)
            )
            key_score = key_matches / len(all_keys)
            # Blend base score with key overlap score
            consistency_score = (base_score + key_score) / 2.0
        else:
            consistency_score = base_score

        # Collect per-key discrepancies
        for key in sorted(all_keys):
            legacy_val = legacy_result.get(key)
            langgraph_val = langgraph_result.get(key)
            if legacy_val != langgraph_val:
                discrepancies.append(
                    f"Key '{key}' differs: legacy={legacy_val!r} "
                    f"langgraph={langgraph_val!r}"
                )

        # Clamp to [0.0, 1.0]
        consistency_score = max(0.0, min(1.0, consistency_score))
        consistent = len(discrepancies) == 0

        # Log discrepancies
        for disc in discrepancies:
            logger.warning(
                "EngineComparisonFramework.compare discrepancy: operation=%s %s",
                operation,
                disc,
            )

        return ComparisonResult(
            consistent=consistent,
            consistency_score=consistency_score,
            discrepancies=discrepancies,
        )

    def compare_analyze(self, task: dict[str, Any]) -> ComparisonMetrics:
        """
        Compare legacy and LangGraph outputs for an *analyze* task.

        Runs both engines, collects their results, and computes
        :class:`ComparisonMetrics`.  Discrepancies are logged.

        Parameters
        ----------
        task:
            Raw task dict.

        Returns
        -------
        ComparisonMetrics
            Comparison metrics for the analyze operation.

        **Validates: Requirements 8.4**
        """
        legacy_result = self._run_legacy_analyze(task)
        langgraph_result = self._run_langgraph_analyze(task)

        metrics = self._compute_metrics(
            intent="analyze",
            legacy_result=legacy_result,
            langgraph_result=langgraph_result,
            consistency_keys=_ANALYZE_CONSISTENCY_KEYS,
        )

        self._log_discrepancies(metrics, task)
        return metrics

    def compare_test(self, task: dict[str, Any]) -> ComparisonMetrics:
        """
        Compare legacy and LangGraph outputs for a *test* task.

        Runs both engines, collects their results, and computes
        :class:`ComparisonMetrics`.  Discrepancies are logged.

        Parameters
        ----------
        task:
            Raw task dict.

        Returns
        -------
        ComparisonMetrics
            Comparison metrics for the test operation.

        **Validates: Requirements 8.4**
        """
        legacy_result = self._run_legacy_test(task)
        langgraph_result = self._run_langgraph_test(task)

        metrics = self._compute_metrics(
            intent="test",
            legacy_result=legacy_result,
            langgraph_result=langgraph_result,
            consistency_keys=_TEST_CONSISTENCY_KEYS,
        )

        self._log_discrepancies(metrics, task)
        return metrics

    def compare_code_change(self, task: dict[str, Any]) -> ComparisonMetrics:
        """
        Compare legacy and LangGraph outputs for a *code_change* task.

        Runs both engines, collects their results, and computes
        :class:`ComparisonMetrics`.  Discrepancies are logged.

        Parameters
        ----------
        task:
            Raw task dict.

        Returns
        -------
        ComparisonMetrics
            Comparison metrics for the code_change operation.

        **Validates: Requirements 8.4, 8.7**
        """
        legacy_result = self._run_legacy_code_change(task)
        langgraph_result = self._run_langgraph_code_change(task)

        metrics = self._compute_metrics(
            intent="code_change",
            legacy_result=legacy_result,
            langgraph_result=langgraph_result,
            consistency_keys=_CODE_CHANGE_CONSISTENCY_KEYS,
        )

        self._log_discrepancies(metrics, task)
        return metrics

    # ------------------------------------------------------------------
    # Engine runners
    # ------------------------------------------------------------------

    def _run_legacy_analyze(self, task: dict[str, Any]) -> EngineResult:
        """Run the legacy analyze handler and return an :class:`EngineResult`."""
        start = time.monotonic()
        try:
            if self._legacy_analyze_handler is not None:
                payload = self._legacy_analyze_handler(task)
            else:
                payload = _default_legacy_analyze(task)
            latency = time.monotonic() - start
            return EngineResult(
                engine="legacy",
                success=True,
                payload=dict(payload) if payload else {},
                latency_seconds=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.monotonic() - start
            logger.warning(
                "EngineComparisonFramework legacy analyze failed: task_id=%s error=%s",
                task.get("task_id"),
                exc,
            )
            return EngineResult(
                engine="legacy",
                success=False,
                payload={},
                latency_seconds=latency,
                error=str(exc),
            )

    def _run_langgraph_analyze(self, task: dict[str, Any]) -> EngineResult:
        """Run the LangGraph analyze workflow and return an :class:`EngineResult`."""
        start = time.monotonic()
        try:
            final_state = self.analyze_workflow.run(task)
            payload = self.analyze_workflow.get_analyze_result(final_state)
            latency = time.monotonic() - start
            return EngineResult(
                engine="langgraph",
                success=bool(payload),
                payload=payload,
                latency_seconds=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.monotonic() - start
            logger.warning(
                "EngineComparisonFramework langgraph analyze failed: task_id=%s error=%s",
                task.get("task_id"),
                exc,
            )
            return EngineResult(
                engine="langgraph",
                success=False,
                payload={},
                latency_seconds=latency,
                error=str(exc),
            )

    def _run_legacy_test(self, task: dict[str, Any]) -> EngineResult:
        """Run the legacy test handler and return an :class:`EngineResult`."""
        start = time.monotonic()
        try:
            if self._legacy_test_handler is not None:
                payload = self._legacy_test_handler(task)
            else:
                payload = _default_legacy_test(task)
            latency = time.monotonic() - start
            return EngineResult(
                engine="legacy",
                success=True,
                payload=dict(payload) if payload else {},
                latency_seconds=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.monotonic() - start
            logger.warning(
                "EngineComparisonFramework legacy test failed: task_id=%s error=%s",
                task.get("task_id"),
                exc,
            )
            return EngineResult(
                engine="legacy",
                success=False,
                payload={},
                latency_seconds=latency,
                error=str(exc),
            )

    def _run_langgraph_test(self, task: dict[str, Any]) -> EngineResult:
        """Run the LangGraph test workflow and return an :class:`EngineResult`."""
        start = time.monotonic()
        try:
            final_state = self.test_workflow.run(task)
            payload = self.test_workflow.get_test_result(final_state)
            latency = time.monotonic() - start
            return EngineResult(
                engine="langgraph",
                success=bool(payload),
                payload=payload,
                latency_seconds=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.monotonic() - start
            logger.warning(
                "EngineComparisonFramework langgraph test failed: task_id=%s error=%s",
                task.get("task_id"),
                exc,
            )
            return EngineResult(
                engine="langgraph",
                success=False,
                payload={},
                latency_seconds=latency,
                error=str(exc),
            )

    def _run_legacy_code_change(self, task: dict[str, Any]) -> EngineResult:
        """Run the legacy code_change handler and return an :class:`EngineResult`."""
        start = time.monotonic()
        try:
            if self._legacy_code_change_handler is not None:
                payload = self._legacy_code_change_handler(task)
            else:
                payload = _default_legacy_code_change(task)
            latency = time.monotonic() - start
            return EngineResult(
                engine="legacy",
                success=True,
                payload=dict(payload) if payload else {},
                latency_seconds=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.monotonic() - start
            logger.warning(
                "EngineComparisonFramework legacy code_change failed: task_id=%s error=%s",
                task.get("task_id"),
                exc,
            )
            return EngineResult(
                engine="legacy",
                success=False,
                payload={},
                latency_seconds=latency,
                error=str(exc),
            )

    def _run_langgraph_code_change(self, task: dict[str, Any]) -> EngineResult:
        """Run the LangGraph code_change workflow and return an :class:`EngineResult`."""
        start = time.monotonic()
        try:
            final_state = self.code_change_workflow.run(task)
            payload = self.code_change_workflow.get_code_change_result(final_state)
            latency = time.monotonic() - start
            return EngineResult(
                engine="langgraph",
                success=bool(payload) and payload.get("success", False),
                payload=payload,
                latency_seconds=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = time.monotonic() - start
            logger.warning(
                "EngineComparisonFramework langgraph code_change failed: task_id=%s error=%s",
                task.get("task_id"),
                exc,
            )
            return EngineResult(
                engine="langgraph",
                success=False,
                payload={},
                latency_seconds=latency,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Metrics computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_metrics(
        *,
        intent: str,
        legacy_result: EngineResult,
        langgraph_result: EngineResult,
        consistency_keys: tuple[str, ...],
    ) -> ComparisonMetrics:
        """
        Compute :class:`ComparisonMetrics` from two :class:`EngineResult` objects.

        Parameters
        ----------
        intent:
            Task intent string.
        legacy_result:
            Result from the legacy engine.
        langgraph_result:
            Result from the LangGraph engine.
        consistency_keys:
            Payload keys to compare for consistency scoring.

        Returns
        -------
        ComparisonMetrics
        """
        successes = sum([legacy_result.success, langgraph_result.success])
        success_rate = successes / 2.0

        # Compute output consistency score
        consistency_score, discrepancies = _compute_consistency(
            legacy_result.payload,
            langgraph_result.payload,
            consistency_keys,
        )

        # Add success mismatch discrepancy
        if legacy_result.success != langgraph_result.success:
            discrepancies.append(
                f"Success mismatch: legacy={legacy_result.success} "
                f"langgraph={langgraph_result.success}"
            )

        # Latency comparison
        legacy_latency = legacy_result.latency_seconds
        langgraph_latency = langgraph_result.latency_seconds
        speedup = (legacy_latency / langgraph_latency) if langgraph_latency > 0 else 0.0

        return ComparisonMetrics(
            intent=intent,
            legacy_success=legacy_result.success,
            langgraph_success=langgraph_result.success,
            success_rate=success_rate,
            output_consistency_score=consistency_score,
            latency_comparison={
                "legacy_seconds": legacy_latency,
                "langgraph_seconds": langgraph_latency,
                "speedup": speedup,
            },
            discrepancies=discrepancies,
        )

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_discrepancies(metrics: ComparisonMetrics, task: dict[str, Any]) -> None:
        """Log any discrepancies found during comparison."""
        task_id = task.get("task_id", "")
        if not metrics.discrepancies:
            logger.info(
                "EngineComparisonFramework: no discrepancies for intent=%s task_id=%s "
                "consistency=%.2f",
                metrics.intent,
                task_id,
                metrics.output_consistency_score,
            )
            return

        for discrepancy in metrics.discrepancies:
            logger.warning(
                "EngineComparisonFramework discrepancy: intent=%s task_id=%s: %s",
                metrics.intent,
                task_id,
                discrepancy,
            )


# ---------------------------------------------------------------------------
# Consistency computation helper
# ---------------------------------------------------------------------------

def _compute_consistency(
    legacy_payload: dict[str, Any],
    langgraph_payload: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[float, list[str]]:
    """
    Compute a consistency score and list of discrepancies between two payloads.

    Compares the specified *keys* in both payloads.  The score is the
    fraction of keys that match (or are both absent).

    Parameters
    ----------
    legacy_payload:
        Payload from the legacy engine.
    langgraph_payload:
        Payload from the LangGraph engine.
    keys:
        Keys to compare.

    Returns
    -------
    tuple[float, list[str]]
        ``(score, discrepancies)`` where score is in [0.0, 1.0].
    """
    if not keys:
        return 1.0, []

    matches = 0
    discrepancies: list[str] = []

    for key in keys:
        legacy_val = legacy_payload.get(key)
        langgraph_val = langgraph_payload.get(key)

        if legacy_val == langgraph_val:
            matches += 1
        else:
            discrepancies.append(
                f"Key '{key}' differs: legacy={legacy_val!r} langgraph={langgraph_val!r}"
            )

    score = matches / len(keys)
    return score, discrepancies


# ---------------------------------------------------------------------------
# Default legacy stubs (used when no handler is injected)
# ---------------------------------------------------------------------------

def _default_legacy_analyze(task: dict[str, Any]) -> dict[str, Any]:
    """
    Default legacy analyze stub that mirrors the format produced by
    ``AgentOrchestrator._build_langgraph_analyze_result``.
    """
    plan_name = str(task.get("planName", "")).strip() or "analyze_plan"
    return {
        "result": "planned",
        "intent": "analyze",
        "planName": plan_name,
        "steps": [],
        "executionPath": "legacy",
    }


def _default_legacy_test(task: dict[str, Any]) -> dict[str, Any]:
    """
    Default legacy test stub that mirrors the format produced by
    ``AgentOrchestrator._execute_langgraph_test`` for a successful run.
    """
    plan_name = str(task.get("planName", "")).strip() or "test_plan"
    test_command = str(task.get("testCommand", "echo test_from_python_agent")).strip()
    return {
        "result": "executed",
        "intent": "test",
        "planName": plan_name,
        "status": "ok",
        "command": test_command,
        "executionPath": "legacy",
    }


def _default_legacy_code_change(task: dict[str, Any]) -> dict[str, Any]:
    """
    Default legacy code_change stub that mirrors the format produced by
    the legacy orchestrator for a successful code_change run.
    """
    plan_name = str(task.get("planName", "")).strip() or "code_change_plan"
    return {
        "result": "applied",
        "intent": "code_change",
        "success": True,
        "planName": plan_name,
        "change_type": "general_change",
        "changes": [],
        "executionPath": "legacy",
    }


# ---------------------------------------------------------------------------
# ComparisonMetricsTracker
# ---------------------------------------------------------------------------

class ComparisonMetricsTracker:
    """
    Accumulates :class:`ComparisonMetrics` over multiple comparisons and
    provides aggregate statistics and automated rollback decisions.

    This tracker is used to monitor the health of the LangGraph migration
    over time.  When the LangGraph success rate drops significantly below
    the legacy success rate, :meth:`should_rollback` returns ``True`` to
    signal that the system should revert to the legacy engine.

    Usage example
    -------------
    ::

        tracker = ComparisonMetricsTracker()
        for task in tasks:
            metrics = framework.compare_code_change(task)
            tracker.record(metrics)

        summary = tracker.get_summary()
        if tracker.should_rollback():
            switch_to_legacy_engine()

    **Validates: Requirements 8.4, 8.7**
    """

    def __init__(self) -> None:
        self._records: list[ComparisonMetrics] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, metrics: ComparisonMetrics) -> None:
        """
        Record a single :class:`ComparisonMetrics` result.

        Parameters
        ----------
        metrics:
            The comparison metrics to accumulate.
        """
        self._records.append(metrics)

    def get_summary(self) -> dict[str, Any]:
        """
        Return aggregate statistics over all recorded comparisons.

        Returns
        -------
        dict with keys:
            total_comparisons : int
                Number of comparisons recorded so far.
            legacy_success_rate : float
                Fraction of comparisons where the legacy engine succeeded.
                In [0.0, 1.0].  Returns 0.0 when no records exist.
            langgraph_success_rate : float
                Fraction of comparisons where the LangGraph engine succeeded.
                In [0.0, 1.0].  Returns 0.0 when no records exist.
            avg_consistency_score : float
                Mean ``output_consistency_score`` across all records.
                In [0.0, 1.0].  Returns 0.0 when no records exist.
            rollback_recommended : bool
                ``True`` when :meth:`should_rollback` returns ``True`` using
                the default threshold (0.1).

        **Validates: Requirements 8.4, 8.7**
        """
        total = len(self._records)
        if total == 0:
            return {
                "total_comparisons": 0,
                "legacy_success_rate": 0.0,
                "langgraph_success_rate": 0.0,
                "avg_consistency_score": 0.0,
                "rollback_recommended": False,
            }

        legacy_successes = sum(1 for r in self._records if r.legacy_success)
        langgraph_successes = sum(1 for r in self._records if r.langgraph_success)
        total_consistency = sum(r.output_consistency_score for r in self._records)

        legacy_success_rate = legacy_successes / total
        langgraph_success_rate = langgraph_successes / total
        avg_consistency_score = total_consistency / total

        # Clamp to [0.0, 1.0] for safety
        avg_consistency_score = max(0.0, min(1.0, avg_consistency_score))

        return {
            "total_comparisons": total,
            "legacy_success_rate": legacy_success_rate,
            "langgraph_success_rate": langgraph_success_rate,
            "avg_consistency_score": avg_consistency_score,
            "rollback_recommended": self.should_rollback(),
        }

    def should_rollback(self, threshold: float = 0.1) -> bool:
        """
        Return ``True`` when the LangGraph success rate has dropped more than
        *threshold* below the legacy success rate.

        This implements the automated rollback trigger described in
        Requirement 8.7: the migration SHALL maintain or improve current
        success rates.

        Parameters
        ----------
        threshold:
            Maximum acceptable gap between legacy and LangGraph success rates.
            Defaults to 0.1 (10 percentage points).

        Returns
        -------
        bool
            ``True`` if rollback is recommended; ``False`` otherwise.
            Always returns ``False`` when no records have been accumulated.

        **Validates: Requirements 8.7**
        """
        if not self._records:
            return False

        total = len(self._records)
        legacy_successes = sum(1 for r in self._records if r.legacy_success)
        langgraph_successes = sum(1 for r in self._records if r.langgraph_success)

        legacy_rate = legacy_successes / total
        langgraph_rate = langgraph_successes / total

        return (legacy_rate - langgraph_rate) > threshold
