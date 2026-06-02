"""
Standardized timeout configuration for the Python Agent.

Defines stage-specific timeouts and maximum execution time limits
to ensure predictable behavior under adverse conditions.

Requirements: 7.1, 7.6
"""
from __future__ import annotations

import signal
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator


# ---------------------------------------------------------------------------
# Stage-specific timeout values (seconds)
# ---------------------------------------------------------------------------

#: Maximum time allowed for the Intent stage (LLM intent classification).
INTENT_TIMEOUT_SECONDS: int = 30

#: Maximum time allowed for the Planner stage (task decomposition).
PLANNER_TIMEOUT_SECONDS: int = 60

#: Maximum time allowed for the Coder stage (code generation).
CODER_TIMEOUT_SECONDS: int = 300

#: Maximum time allowed for the Reviewer stage (code review).
REVIEWER_TIMEOUT_SECONDS: int = 120

#: Maximum time allowed for the Tester stage (test execution).
TESTER_TIMEOUT_SECONDS: int = 180

#: Absolute maximum execution time for any task (30 minutes).
MAX_TASK_EXECUTION_SECONDS: int = 30 * 60  # 1800 seconds


# ---------------------------------------------------------------------------
# Stage name constants
# ---------------------------------------------------------------------------

STAGE_INTENT = "intent"
STAGE_PLANNER = "planner"
STAGE_CODER = "coder"
STAGE_REVIEWER = "reviewer"
STAGE_TESTER = "tester"


# ---------------------------------------------------------------------------
# Timeout configuration dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StageTimeoutConfig:
    """Immutable configuration for a single pipeline stage timeout."""

    stage: str
    timeout_seconds: int

    def __post_init__(self) -> None:
        if not self.stage or not self.stage.strip():
            raise ValueError("stage must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")


@dataclass(frozen=True)
class TimeoutConfig:
    """
    Complete timeout configuration for all pipeline stages.

    Provides stage-specific timeouts and the global maximum execution
    time limit with automatic termination support.

    Requirements: 7.1, 7.6
    """

    intent: StageTimeoutConfig
    planner: StageTimeoutConfig
    coder: StageTimeoutConfig
    reviewer: StageTimeoutConfig
    tester: StageTimeoutConfig
    max_task_execution_seconds: int

    def get_stage_timeout(self, stage: str) -> int:
        """
        Return the timeout in seconds for the given stage name.

        :param stage: One of 'intent', 'planner', 'coder', 'reviewer', 'tester'.
        :returns: Timeout in seconds.
        :raises ValueError: If the stage name is not recognised.
        """
        stage_lower = (stage or "").strip().lower()
        mapping = {
            STAGE_INTENT: self.intent.timeout_seconds,
            STAGE_PLANNER: self.planner.timeout_seconds,
            STAGE_CODER: self.coder.timeout_seconds,
            STAGE_REVIEWER: self.reviewer.timeout_seconds,
            STAGE_TESTER: self.tester.timeout_seconds,
        }
        if stage_lower not in mapping:
            raise ValueError(
                f"Unknown stage '{stage}'. Valid stages: {sorted(mapping.keys())}"
            )
        return mapping[stage_lower]

    def all_stages(self) -> list[StageTimeoutConfig]:
        """Return all stage timeout configurations as a list."""
        return [self.intent, self.planner, self.coder, self.reviewer, self.tester]


# ---------------------------------------------------------------------------
# Default configuration instance
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_CONFIG = TimeoutConfig(
    intent=StageTimeoutConfig(stage=STAGE_INTENT, timeout_seconds=INTENT_TIMEOUT_SECONDS),
    planner=StageTimeoutConfig(stage=STAGE_PLANNER, timeout_seconds=PLANNER_TIMEOUT_SECONDS),
    coder=StageTimeoutConfig(stage=STAGE_CODER, timeout_seconds=CODER_TIMEOUT_SECONDS),
    reviewer=StageTimeoutConfig(stage=STAGE_REVIEWER, timeout_seconds=REVIEWER_TIMEOUT_SECONDS),
    tester=StageTimeoutConfig(stage=STAGE_TESTER, timeout_seconds=TESTER_TIMEOUT_SECONDS),
    max_task_execution_seconds=MAX_TASK_EXECUTION_SECONDS,
)


# ---------------------------------------------------------------------------
# Timeout enforcement utilities
# ---------------------------------------------------------------------------

class TimeoutError(RuntimeError):
    """Raised when a stage or task execution exceeds its configured timeout."""

    def __init__(self, stage: str, timeout_seconds: int, task_id: str = "") -> None:
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        self.task_id = task_id
        detail = f"task_id={task_id!r}, " if task_id else ""
        super().__init__(
            f"Timeout exceeded: {detail}stage={stage!r}, limit={timeout_seconds}s"
        )


class _TimeoutThread(threading.Thread):
    """Background thread that raises TimeoutError after a deadline."""

    def __init__(self, stage: str, timeout_seconds: int, task_id: str) -> None:
        super().__init__(daemon=True)
        self._stage = stage
        self._timeout_seconds = timeout_seconds
        self._task_id = task_id
        self._cancelled = threading.Event()
        self._timed_out = False

    def run(self) -> None:
        fired = not self._cancelled.wait(timeout=self._timeout_seconds)
        if fired:
            self._timed_out = True

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def timed_out(self) -> bool:
        return self._timed_out


@contextmanager
def stage_timeout(
    stage: str,
    timeout_seconds: int,
    *,
    task_id: str = "",
    config: TimeoutConfig | None = None,
) -> Generator[None, None, None]:
    """
    Context manager that enforces a stage-level timeout.

    On POSIX systems the implementation uses ``signal.alarm`` for accurate
    enforcement.  On Windows (where SIGALRM is unavailable) a background
    thread tracks the deadline; the timeout is detected *after* the block
    exits rather than interrupting it mid-execution, which is sufficient for
    property-based testing and unit tests.

    :param stage: Pipeline stage name (used in error messages and logging).
    :param timeout_seconds: Maximum allowed duration in seconds.
    :param task_id: Optional task identifier for structured error messages.
    :param config: Optional :class:`TimeoutConfig` to look up the timeout
        from a stage name instead of providing it directly.
    :raises TimeoutError: If the block takes longer than *timeout_seconds*.

    Requirements: 7.1
    """
    effective_timeout = timeout_seconds
    if config is not None:
        try:
            effective_timeout = config.get_stage_timeout(stage)
        except ValueError:
            pass  # Fall back to the explicitly provided value

    if effective_timeout <= 0:
        raise ValueError(f"timeout_seconds must be positive, got {effective_timeout}")

    # POSIX path: use SIGALRM for accurate preemption
    if hasattr(signal, "SIGALRM"):
        def _handler(signum: int, frame: object) -> None:  # noqa: ARG001
            raise TimeoutError(stage, effective_timeout, task_id)

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(effective_timeout)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Non-POSIX path: use a background thread to detect timeouts
        watcher = _TimeoutThread(stage, effective_timeout, task_id)
        watcher.start()
        try:
            yield
        finally:
            watcher.cancel()
            watcher.join(timeout=0.1)
            if watcher.timed_out:
                raise TimeoutError(stage, effective_timeout, task_id)


def get_stage_timeout(stage: str, config: TimeoutConfig | None = None) -> int:
    """
    Convenience function to retrieve the timeout for a named stage.

    Uses :data:`DEFAULT_TIMEOUT_CONFIG` when *config* is not provided.

    :param stage: Pipeline stage name.
    :param config: Optional custom :class:`TimeoutConfig`.
    :returns: Timeout in seconds.
    :raises ValueError: If the stage name is not recognised.
    """
    effective_config = config if config is not None else DEFAULT_TIMEOUT_CONFIG
    return effective_config.get_stage_timeout(stage)
