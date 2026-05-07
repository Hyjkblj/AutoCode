"""
Prometheus metrics for the Python Agent.

Exposes counters and histograms for:
- Task lifecycle events (creation, completion, duration)
- Event delivery success, retry, and failure rates
- Backend generation success rates and validation failure categories

**Validates: Requirements 10.1, 10.2, 10.3**
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, CollectorRegistry, REGISTRY


# ---------------------------------------------------------------------------
# Default registry
# ---------------------------------------------------------------------------

def _get_registry(registry: CollectorRegistry | None) -> CollectorRegistry:
    return registry if registry is not None else REGISTRY


# ---------------------------------------------------------------------------
# TaskMetrics
# ---------------------------------------------------------------------------

class TaskMetrics:
    """
    Prometheus metrics for task lifecycle events.

    Tracks task creation, completion, and duration as required by
    Requirement 10.1.

    **Validates: Requirements 10.1**
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        reg = _get_registry(registry)

        self.task_created_total = Counter(
            "task_created_total",
            "Total number of tasks created, labelled by intent.",
            ["intent"],
            registry=reg,
        )

        self.task_completed_total = Counter(
            "task_completed_total",
            "Total number of tasks completed, labelled by intent and result.",
            ["intent", "result"],
            registry=reg,
        )

        self.task_duration_seconds = Histogram(
            "task_duration_seconds",
            "Task execution duration in seconds, labelled by intent.",
            ["intent"],
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800),
            registry=reg,
        )

    def record_task_created(self, intent: str) -> None:
        """Increment the task_created_total counter for the given intent."""
        self.task_created_total.labels(intent=intent).inc()

    def record_task_completed(self, intent: str, result: str) -> None:
        """
        Increment the task_completed_total counter.

        :param intent: Task intent (e.g. "backend_generation", "analyze").
        :param result: Outcome label, e.g. "success" or "failed".
        """
        self.task_completed_total.labels(intent=intent, result=result).inc()

    def record_task_duration(self, intent: str, duration_seconds: float) -> None:
        """
        Observe a task duration in the histogram.

        :param intent: Task intent.
        :param duration_seconds: Elapsed time in seconds (must be >= 0).
        """
        self.task_duration_seconds.labels(intent=intent).observe(
            max(0.0, float(duration_seconds))
        )


# ---------------------------------------------------------------------------
# EventMetrics
# ---------------------------------------------------------------------------

class EventMetrics:
    """
    Prometheus metrics for event delivery.

    Tracks delivery success, retry, and failure rates as required by
    Requirement 10.2.

    **Validates: Requirements 10.2**
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        reg = _get_registry(registry)

        self.event_delivery_total = Counter(
            "event_delivery_total",
            "Total event delivery attempts, labelled by status (success/retry/failed).",
            ["status"],
            registry=reg,
        )

        self.event_retry_total = Counter(
            "event_retry_total",
            "Total number of event delivery retries.",
            registry=reg,
        )

    def record_delivery(self, status: str) -> None:
        """
        Record an event delivery attempt.

        :param status: One of "success", "retry", or "failed".
        """
        self.event_delivery_total.labels(status=status).inc()

    def record_delivery_success(self) -> None:
        """Convenience method: record a successful delivery."""
        self.record_delivery("success")

    def record_delivery_retry(self) -> None:
        """Convenience method: record a retry attempt (increments both counters)."""
        self.record_delivery("retry")
        self.event_retry_total.inc()

    def record_delivery_failed(self) -> None:
        """Convenience method: record a final delivery failure."""
        self.record_delivery("failed")


# ---------------------------------------------------------------------------
# GenerationMetrics
# ---------------------------------------------------------------------------

class GenerationMetrics:
    """
    Prometheus metrics for backend code generation.

    Tracks generation success rates and validation failure categories as
    required by Requirement 10.3.

    **Validates: Requirements 10.3**
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        reg = _get_registry(registry)

        self.generation_total = Counter(
            "generation_total",
            "Total generation attempts, labelled by type and result.",
            ["type", "result"],
            registry=reg,
        )

        self.validation_failure_total = Counter(
            "validation_failure_total",
            "Total validation failures, labelled by category.",
            ["category"],
            registry=reg,
        )

    def record_generation(self, gen_type: str, result: str) -> None:
        """
        Record a generation attempt.

        :param gen_type: Generation type, e.g. "backend" or "fullstack".
        :param result: Outcome, e.g. "success" or "failed".
        """
        self.generation_total.labels(type=gen_type, result=result).inc()

    def record_generation_success(self, gen_type: str) -> None:
        """Convenience method: record a successful generation."""
        self.record_generation(gen_type, "success")

    def record_generation_failed(self, gen_type: str) -> None:
        """Convenience method: record a failed generation."""
        self.record_generation(gen_type, "failed")

    def record_validation_failure(self, category: str) -> None:
        """
        Record a validation failure.

        :param category: One of "syntax", "structure", "dependency", or "runtime".
        """
        self.validation_failure_total.labels(category=category).inc()


# ---------------------------------------------------------------------------
# PipelineMetrics — AI generation pipeline observability
# ---------------------------------------------------------------------------

class PipelineMetrics:
    """
    Prometheus metrics for the AI generation pipeline.

    Tracks per-stage duration/throughput, input language distribution,
    and failure classification by error taxonomy.

    **Validates: Requirements 10.1, 10.3**
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        reg = _get_registry(registry)

        self.pipeline_stage_duration_seconds = Histogram(
            "pipeline_stage_duration_seconds",
            "Duration of each pipeline stage in seconds.",
            ["stage", "status"],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
            registry=reg,
        )

        self.pipeline_stage_total = Counter(
            "pipeline_stage_total",
            "Total pipeline stage executions, labelled by stage and status.",
            ["stage", "status"],
            registry=reg,
        )

        self.input_language_total = Counter(
            "input_language_total",
            "Total tasks bucketed by detected input language.",
            ["language"],
            registry=reg,
        )

        self.failure_class_total = Counter(
            "failure_class_total",
            "Total failures by error taxonomy class.",
            ["error_class"],
            registry=reg,
        )

    def record_stage(self, stage: str, status: str, duration_seconds: float) -> None:
        """Record a pipeline stage execution with duration."""
        self.pipeline_stage_duration_seconds.labels(stage=stage, status=status).observe(
            max(0.0, float(duration_seconds))
        )
        self.pipeline_stage_total.labels(stage=stage, status=status).inc()

    def record_input_language(self, language: str) -> None:
        """Record detected input language for a task."""
        self.input_language_total.labels(language=language).inc()

    def record_failure_class(self, error_class: str) -> None:
        """Record a failure by error taxonomy class (llm, sandbox, validation, protocol, plugin)."""
        self.failure_class_total.labels(error_class=error_class).inc()
