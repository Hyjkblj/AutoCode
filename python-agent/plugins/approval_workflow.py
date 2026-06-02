"""
Plugin approval workflow integration.

Validates: Requirements 13.2 (RBAC), 13.3 (Audit Trail)
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

from client.control_plane_client import ControlPlaneClient
from plugins.contracts import PluginContext, PluginManifest


@dataclass(frozen=True)
class PluginApprovalRequest:
    """Request for plugin execution approval."""
    
    approval_id: str
    task_id: str
    trace_id: str
    run_id: str
    plugin_id: str
    plugin_version: str
    action: str
    reason: str
    risk_score: float
    context: dict[str, Any]
    required_policies: list[str]
    timeout_seconds: int = 300
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API request."""
        return {
            "approvalId": self.approval_id,
            "taskId": self.task_id,
            "traceId": self.trace_id,
            "runId": self.run_id,
            "action": self.action,
            "tool": f"plugin:{self.plugin_id}",
            "reason": self.reason,
            "riskScore": self.risk_score,
            "context": self.context,
            "requiredPolicies": self.required_policies,
            "timeoutSeconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class PluginApprovalDecision:
    """Decision for plugin execution approval."""
    
    approval_id: str
    decision: str  # APPROVED, REJECTED, EXPIRED
    message: str | None = None
    decided_by: str | None = None


class PluginApprovalWorkflow:
    """Manages plugin approval workflow and security gates."""
    
    def __init__(
        self,
        client: ControlPlaneClient | None = None,
        auto_approve_low_risk: bool = True,
        risk_threshold: float = 0.5,
    ) -> None:
        self.client = client
        self.auto_approve_low_risk = auto_approve_low_risk
        self.risk_threshold = risk_threshold
    
    def requires_approval(
        self,
        manifest: PluginManifest,
        context: PluginContext,
    ) -> bool:
        """
        Check if plugin execution requires approval.
        
        Args:
            manifest: Plugin manifest with permissions
            context: Plugin execution context
            
        Returns:
            True if approval is required, False otherwise
        """
        # High-risk permissions always require approval
        if manifest.permissions.sandbox_exec:
            return True
        if manifest.permissions.network_access:
            return True
        
        # Workspace write requires approval unless auto-approved
        if manifest.permissions.workspace_write:
            risk_score = self._calculate_risk_score(manifest, context)
            if risk_score >= self.risk_threshold:
                return True
            if not self.auto_approve_low_risk:
                return True
        
        return False
    
    def request_approval(
        self,
        manifest: PluginManifest,
        context: PluginContext,
    ) -> PluginApprovalRequest:
        """
        Create an approval request for plugin execution.
        
        Args:
            manifest: Plugin manifest
            context: Plugin execution context
            
        Returns:
            Approval request object
        """
        task_id = str(context.task.get("taskId", "unknown"))
        trace_id = str(context.task.get("traceId", str(uuid.uuid4())))
        run_id = str(context.task.get("runId", str(uuid.uuid4())))
        
        risk_score = self._calculate_risk_score(manifest, context)
        required_policies = self._determine_required_policies(manifest)
        
        return PluginApprovalRequest(
            approval_id=str(uuid.uuid4()),
            task_id=task_id,
            trace_id=trace_id,
            run_id=run_id,
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            action="plugin_execution",
            reason=self._generate_approval_reason(manifest),
            risk_score=risk_score,
            context={
                "plugin_id": manifest.plugin_id,
                "plugin_version": manifest.version,
                "plugin_type": manifest.plugin_type,
                "permissions": {
                    "workspace_read": manifest.permissions.workspace_read,
                    "workspace_write": manifest.permissions.workspace_write,
                    "sandbox_exec": manifest.permissions.sandbox_exec,
                    "network_access": manifest.permissions.network_access,
                },
                "capabilities": list(manifest.capabilities),
                "timeout_seconds": manifest.timeout_seconds,
            },
            required_policies=required_policies,
            timeout_seconds=300,
        )
    
    def submit_approval_request(
        self,
        request: PluginApprovalRequest,
    ) -> str:
        """
        Submit approval request to approval service.
        
        Args:
            request: Approval request
            
        Returns:
            Approval ID
            
        Raises:
            RuntimeError: If submission fails
        """
        if not self.client:
            raise RuntimeError("Control plane client not configured")
        
        try:
            # Submit to approval service via control plane
            response = self.client.post(
                "/api/approvals",
                json=request.to_dict(),
            )
            return request.approval_id
        except Exception as e:
            raise RuntimeError(f"Failed to submit approval request: {e}")
    
    def check_approval_status(
        self,
        approval_id: str,
    ) -> PluginApprovalDecision:
        """
        Check the status of an approval request.
        
        Args:
            approval_id: Approval request ID
            
        Returns:
            Approval decision
            
        Raises:
            RuntimeError: If check fails
        """
        if not self.client:
            raise RuntimeError("Control plane client not configured")
        
        try:
            response = self.client.get(f"/api/approvals/{approval_id}")
            data = response.json()
            
            return PluginApprovalDecision(
                approval_id=approval_id,
                decision=data.get("decision", "PENDING"),
                message=data.get("decisionMessage"),
                decided_by=data.get("decidedBy"),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to check approval status: {e}")
    
    def _calculate_risk_score(
        self,
        manifest: PluginManifest,
        context: PluginContext,
    ) -> float:
        """
        Calculate risk score for plugin execution.
        
        Risk factors:
        - Sandbox execution: +0.4
        - Network access: +0.3
        - Workspace write: +0.2
        - Unknown plugin: +0.1
        
        Returns:
            Risk score between 0.0 and 1.0
        """
        score = 0.0
        
        if manifest.permissions.sandbox_exec:
            score += 0.4
        if manifest.permissions.network_access:
            score += 0.3
        if manifest.permissions.workspace_write:
            score += 0.2
        
        # Check if plugin is from trusted source
        if not manifest.plugin_id.startswith("builtin."):
            score += 0.1
        
        return min(1.0, score)
    
    def _determine_required_policies(
        self,
        manifest: PluginManifest,
    ) -> list[str]:
        """Determine required RBAC policies for plugin execution."""
        policies = ["plugin:execute"]
        
        if manifest.permissions.workspace_write:
            policies.append("plugin:workspace_write")
        if manifest.permissions.sandbox_exec:
            policies.append("plugin:sandbox_exec")
        if manifest.permissions.network_access:
            policies.append("plugin:network_access")
        
        return policies
    
    def _generate_approval_reason(
        self,
        manifest: PluginManifest,
    ) -> str:
        """Generate human-readable approval reason."""
        permissions = []
        if manifest.permissions.workspace_write:
            permissions.append("workspace write")
        if manifest.permissions.sandbox_exec:
            permissions.append("sandbox execution")
        if manifest.permissions.network_access:
            permissions.append("network access")
        
        perm_str = ", ".join(permissions) if permissions else "read-only"
        
        return (
            f"Plugin '{manifest.plugin_id}' (v{manifest.version}) "
            f"requires approval for {perm_str} permissions"
        )
