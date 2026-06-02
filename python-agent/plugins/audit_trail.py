"""
Plugin audit trail and compliance logging.

Validates: Requirements 13.3 (Audit Trail Completeness), 13.6 (Security Incident Response)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from plugins.contracts import PluginManifest


logger = logging.getLogger(__name__)


@dataclass
class PluginAuditEvent:
    """Audit event for plugin operations."""
    
    event_type: str
    plugin_id: str
    plugin_version: str
    task_id: str
    trace_id: str
    run_id: str
    timestamp: str
    user_id: str | None = None
    decision: str | None = None
    risk_score: float | None = None
    resource_usage: dict[str, Any] | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        data = asdict(self)
        # Remove None values for cleaner logs
        return {k: v for k, v in data.items() if v is not None}
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class PluginAuditTrail:
    """Manages audit trail for plugin operations."""
    
    def __init__(self, logger_name: str = "plugin_audit") -> None:
        self.audit_logger = logging.getLogger(logger_name)
        # Ensure audit logger is configured
        if not self.audit_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - PLUGIN_AUDIT - %(levelname)s - %(message)s"
                )
            )
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)
    
    def log_plugin_loaded(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
    ) -> None:
        """Log plugin loading event."""
        event = PluginAuditEvent(
            event_type="plugin_loaded",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            metadata={
                "plugin_type": manifest.plugin_type,
                "enabled": manifest.enabled,
                "priority": manifest.priority,
                "capabilities": list(manifest.capabilities),
                "permissions": {
                    "workspace_read": manifest.permissions.workspace_read,
                    "workspace_write": manifest.permissions.workspace_write,
                    "sandbox_exec": manifest.permissions.sandbox_exec,
                    "network_access": manifest.permissions.network_access,
                },
            },
        )
        self._log_event(event, logging.INFO)
    
    def log_plugin_execution_started(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
    ) -> None:
        """Log plugin execution start."""
        event = PluginAuditEvent(
            event_type="plugin_execution_started",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
        )
        self._log_event(event, logging.INFO)
    
    def log_plugin_execution_completed(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        resource_usage: dict[str, Any] | None = None,
    ) -> None:
        """Log plugin execution completion."""
        event = PluginAuditEvent(
            event_type="plugin_execution_completed",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            resource_usage=resource_usage,
        )
        self._log_event(event, logging.INFO)
    
    def log_plugin_execution_failed(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        error_message: str,
        resource_usage: dict[str, Any] | None = None,
    ) -> None:
        """Log plugin execution failure."""
        event = PluginAuditEvent(
            event_type="plugin_execution_failed",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            error_message=error_message,
            resource_usage=resource_usage,
        )
        self._log_event(event, logging.ERROR)
    
    def log_approval_requested(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        approval_id: str,
        risk_score: float,
    ) -> None:
        """Log approval request."""
        event = PluginAuditEvent(
            event_type="plugin_approval_requested",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            risk_score=risk_score,
            metadata={"approval_id": approval_id},
        )
        self._log_event(event, logging.INFO)
    
    def log_approval_decision(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        approval_id: str,
        decision: str,
        decided_by: str | None = None,
    ) -> None:
        """Log approval decision."""
        event = PluginAuditEvent(
            event_type="plugin_approval_decision",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            decision=decision,
            user_id=decided_by,
            metadata={"approval_id": approval_id},
        )
        self._log_event(event, logging.INFO)
    
    def log_security_violation(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        violation_type: str,
        details: str,
    ) -> None:
        """Log security violation."""
        event = PluginAuditEvent(
            event_type="plugin_security_violation",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            error_message=details,
            metadata={"violation_type": violation_type},
        )
        self._log_event(event, logging.WARNING)
    
    def log_resource_limit_exceeded(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        limit_type: str,
        limit_value: Any,
        actual_value: Any,
    ) -> None:
        """Log resource limit exceeded."""
        event = PluginAuditEvent(
            event_type="plugin_resource_limit_exceeded",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            error_message=f"Resource limit exceeded: {limit_type}",
            metadata={
                "limit_type": limit_type,
                "limit_value": limit_value,
                "actual_value": actual_value,
            },
        )
        self._log_event(event, logging.WARNING)
    
    def log_circuit_breaker_opened(
        self,
        manifest: PluginManifest,
        task_id: str,
        trace_id: str,
        run_id: str,
        failure_count: int,
    ) -> None:
        """Log circuit breaker opened."""
        event = PluginAuditEvent(
            event_type="plugin_circuit_breaker_opened",
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            timestamp=self._now(),
            metadata={"failure_count": failure_count},
        )
        self._log_event(event, logging.WARNING)
    
    def _log_event(self, event: PluginAuditEvent, level: int) -> None:
        """Log audit event at specified level."""
        self.audit_logger.log(level, event.to_json())
    
    def _now(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().isoformat() + "Z"
