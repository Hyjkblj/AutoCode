from __future__ import annotations

import logging
from collections import defaultdict
from contextlib import contextmanager
from time import monotonic
from typing import Any, Iterator
from uuid import uuid4

from utils.metrics import PipelineMetrics

_logger = logging.getLogger(__name__)

# Module-level singleton; safe because prometheus_client is process-global.
_pipeline_metrics = PipelineMetrics()


class TaskObservability:
    def __init__(self, *, task_id: str, trace_id: str, run_id: str, engine: str) -> None:
        self.task_id = task_id
        self.trace_id = trace_id
        self.run_id = run_id
        self.engine = engine or "legacy"
        self.started_at = monotonic()
        self._spans: list[dict[str, Any]] = []
        self._metrics: dict[tuple[str, str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._summary: dict[str, Any] | None = None

    @contextmanager
    def span(
        self,
        name: str,
        *,
        stage: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[None]:
        started_at = monotonic()
        normalized_attributes = _normalize_attributes(attributes or {})
        status = "ok"
        try:
            yield
        except Exception as exc:  # noqa: BLE001
            status = "error"
            normalized_attributes.setdefault("error", str(exc))
            raise
        finally:
            duration_s = max(0.0, monotonic() - started_at)
            safe_name = _safe_text(name, fallback="unknown_span")
            safe_stage = _safe_text(stage, fallback="unknown_stage")
            self._spans.append(
                {
                    "name": safe_name,
                    "stage": safe_stage,
                    "status": status,
                    "durationMs": max(0, int(duration_s * 1000)),
                    "attributes": normalized_attributes,
                }
            )
            # Emit Prometheus metrics for this stage
            try:
                _pipeline_metrics.record_stage(safe_stage, status, duration_s)
            except Exception:  # noqa: BLE001 — never break the caller over metrics
                pass

    def record_metric(self, name: str, value: float = 1, *, unit: str = "count", **tags: Any) -> None:
        metric_name = _safe_text(name, fallback="unknown_metric")
        metric_unit = _safe_text(unit, fallback="count")
        normalized_tags = _normalize_tags(tags)
        key = (metric_name, metric_unit, tuple(sorted(normalized_tags.items())))
        self._metrics[key] += float(value)

    def record_event_publish(self, event_type: str, *, attempts: int = 1) -> None:
        safe_event_type = _safe_text(event_type, fallback="unknown_event")
        safe_attempts = max(1, int(attempts))
        self.record_metric("event_publish_total", 1, unit="count", eventType=safe_event_type, engine=self.engine)
        self.record_metric(
            "event_publish_attempts_total",
            safe_attempts,
            unit="count",
            eventType=safe_event_type,
            engine=self.engine,
        )

    def finalize(
        self,
        *,
        task_status: str,
        intent: str = "",
        reason: str = "",
        generation_target: str = "",
        fix_loop_attempts: int = 0,
        fix_loop_success: bool | None = None,
    ) -> dict[str, Any]:
        if self._summary is not None:
            return _copy_summary(self._summary)

        safe_task_status = _safe_text(task_status, fallback="unknown")
        safe_intent = _safe_text(intent, fallback="unknown")
        self.record_metric("task_total", 1, unit="count", status=safe_task_status, intent=safe_intent, engine=self.engine)

        safe_generation_target = _safe_text(generation_target)
        if safe_generation_target:
            self.record_metric(
                "generation_total",
                1,
                unit="count",
                status=safe_task_status,
                target=safe_generation_target,
                engine=self.engine,
            )

        if fix_loop_attempts > 0 or fix_loop_success is not None:
            fix_status = "success" if fix_loop_success else "failed"
            self.record_metric(
                "fix_loop_total",
                1,
                unit="count",
                status=fix_status,
                intent=safe_intent,
                engine=self.engine,
            )
            self.record_metric(
                "fix_loop_attempts_total",
                max(0, int(fix_loop_attempts)),
                unit="count",
                status=fix_status,
                intent=safe_intent,
                engine=self.engine,
            )

        summary: dict[str, Any] = {
            "traceId": self.trace_id,
            "runId": self.run_id,
            "engine": self.engine,
            "taskStatus": safe_task_status,
            "intent": safe_intent,
            "totalDurationMs": max(0, int((monotonic() - self.started_at) * 1000)),
            "spanCount": len(self._spans),
            "spans": [dict(item) for item in self._spans],
            "metrics": _export_metrics(self._metrics),
        }
        safe_reason = _safe_text(reason)
        if safe_reason:
            summary["reason"] = safe_reason
        self._summary = summary
        return _copy_summary(summary)


def ensure_task_observability(task: dict[str, Any], *, engine: str = "") -> TaskObservability:
    existing = task.get("_observability")
    if isinstance(existing, TaskObservability):
        return existing

    task_id = _safe_text(task.get("taskId"), fallback="task")
    trace_id = _safe_text(task.get("traceId")) or f"trc_{task_id}_{uuid4().hex[:8]}"
    run_id = _safe_text(task.get("runId")) or f"run_{task_id}_{uuid4().hex[:8]}"
    resolved_engine = _safe_text(engine or task.get("_agentEngine") or task.get("engine"), fallback="legacy")
    observation = TaskObservability(task_id=task_id, trace_id=trace_id, run_id=run_id, engine=resolved_engine)
    task["_observability"] = observation
    task["traceId"] = trace_id
    task["runId"] = run_id
    return observation


def observe_task_span(
    task: dict[str, Any],
    name: str,
    *,
    stage: str,
    attributes: dict[str, Any] | None = None,
):
    observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
    return observation.span(name, stage=stage, attributes=attributes)


def enrich_payload(task: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
    enriched = dict(payload)
    current_trace = _safe_text(enriched.get("traceId"))
    current_run = _safe_text(enriched.get("runId"))
    if current_trace and current_trace != observation.trace_id:
        enriched.setdefault("taskTraceId", observation.trace_id)
    else:
        enriched["traceId"] = observation.trace_id
    if current_run and current_run != observation.run_id:
        enriched.setdefault("taskRunId", observation.run_id)
    else:
        enriched["runId"] = observation.run_id
    enriched.setdefault("engine", observation.engine)
    return enriched


def record_event_publish(task: dict[str, Any], event_type: str, *, attempts: int = 1) -> None:
    observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
    observation.record_event_publish(event_type, attempts=attempts)


def attach_terminal_observability(
    task: dict[str, Any],
    payload: dict[str, Any],
    *,
    task_status: str,
    intent: str = "",
    reason: str = "",
    generation_target: str = "",
    fix_loop_attempts: int = 0,
    fix_loop_success: bool | None = None,
) -> dict[str, Any]:
    observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
    output = dict(payload)
    output["observability"] = observation.finalize(
        task_status=task_status,
        intent=intent,
        reason=reason,
        generation_target=generation_target,
        fix_loop_attempts=fix_loop_attempts,
        fix_loop_success=fix_loop_success,
    )
    return output


def _safe_text(value: Any, *, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _normalize_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in attributes.items():
        safe_key = _safe_text(key)
        if not safe_key:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            normalized[safe_key] = value
            continue
        normalized[safe_key] = str(value)
    return normalized


def _normalize_tags(tags: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in tags.items():
        safe_key = _safe_text(key)
        safe_value = _safe_text(value)
        if not safe_key or not safe_value:
            continue
        normalized[safe_key] = safe_value
    return normalized


def _export_metrics(metrics: dict[tuple[str, str, tuple[tuple[str, str], ...]], float]) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for (name, unit, tag_items), value in sorted(metrics.items()):
        exported.append(
            {
                "name": name,
                "unit": unit,
                "value": int(value) if float(value).is_integer() else round(value, 3),
                "tags": dict(tag_items),
            }
        )
    return exported


def _copy_summary(summary: dict[str, Any]) -> dict[str, Any]:
    output = dict(summary)
    output["spans"] = [dict(item) for item in summary.get("spans", []) if isinstance(item, dict)]
    output["metrics"] = [dict(item) for item in summary.get("metrics", []) if isinstance(item, dict)]
    return output


# ---------------------------------------------------------------------------
# Prometheus metric helpers (called from orchestrator / workflow)
# ---------------------------------------------------------------------------

def record_input_language(language: str) -> None:
    """Record detected input language for a task (e.g. 'python', 'javascript', 'unknown')."""
    try:
        _pipeline_metrics.record_input_language(language)
    except Exception:  # noqa: BLE001
        pass


def record_failure_class(error_class: str) -> None:
    """Record a failure by error taxonomy class (llm, sandbox, validation, protocol, plugin)."""
    try:
        _pipeline_metrics.record_failure_class(error_class)
    except Exception:  # noqa: BLE001
        pass


def log_fix_loop_attempt(
    task: dict[str, Any],
    *,
    attempt: int,
    max_attempts: int,
    success: bool,
    error: str = "",
) -> None:
    """Log a fix-loop iteration and record observability metrics."""
    observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
    status = "success" if success else "failed"
    observation.record_metric(
        "fix_loop_attempt_total",
        1,
        unit="count",
        status=status,
        attempt=str(attempt),
        engine=observation.engine,
    )
    _logger.info(
        "fix_loop_attempt task_id=%s attempt=%d/%d success=%s error=%s",
        observation.task_id,
        attempt,
        max_attempts,
        success,
        error,
    )


def log_structured(
    task: dict[str, Any],
    *,
    level: str,
    message: str,
    stage: str = "",
    **extra: Any,
) -> None:
    """Emit a structured log entry enriched with task context."""
    observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
    log_fn = getattr(_logger, level, _logger.info)
    fields = " ".join(f"{k}={v}" for k, v in extra.items())
    stage_part = f" stage={stage}" if stage else ""
    log_fn(
        "%s task_id=%s trace_id=%s run_id=%s%s %s",
        message,
        observation.task_id,
        observation.trace_id,
        observation.run_id,
        stage_part,
        fields,
    )
