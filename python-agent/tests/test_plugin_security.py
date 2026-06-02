"""
Unit tests for plugin security features.

Validates: Requirements 13.1 (Security Policy), 13.2 (RBAC), 13.3 (Audit Trail)
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import time

from plugins.approval_workflow import PluginApprovalWorkflow, PluginApprovalRequest
from plugins.audit_trail import PluginAuditTrail, PluginAuditEvent
from plugins.contracts import PluginManifest, PluginPermissions, PluginContext
from plugins.resource_limits import (
    PluginIsolationManager,
    ResourceLimits,
    ResourceLimitExceeded,
)


class TestResourceLimits:
    """Test resource limits and isolation."""
    
    def test_resource_limits_from_env(self):
        """Test loading resource limits from environment."""
        limits = ResourceLimits.from_env()
        assert limits.max_memory_mb > 0
        assert limits.max_cpu_time_seconds > 0
        assert limits.max_wall_time_seconds > 0
    
    def test_custom_resource_limits(self):
        """Test custom resource limits."""
        limits = ResourceLimits(
            max_memory_mb=256,
            max_cpu_time_seconds=15,
            max_wall_time_seconds=30,
        )
        assert limits.max_memory_mb == 256
        assert limits.max_cpu_time_seconds == 15
        assert limits.max_wall_time_seconds == 30
    
    def test_execute_with_limits_success(self):
        """Test successful execution within limits."""
        manager = PluginIsolationManager()
        
        def fast_operation():
            return "success"
        
        result = manager.execute_with_limits("test-plugin", fast_operation)
        assert result == "success"
    
    def test_execute_with_limits_timeout(self):
        """Test timeout enforcement."""
        manager = PluginIsolationManager()
        
        def slow_operation():
            time.sleep(5)
            return "should not reach here"
        
        with pytest.raises(TimeoutError):
            manager.execute_with_limits("test-plugin", slow_operation, timeout_seconds=1)
    
    def test_get_resource_usage(self):
        """Test resource usage reporting."""
        manager = PluginIsolationManager()
        usage = manager.get_resource_usage()
        
        assert "user_cpu_time_seconds" in usage
        assert "system_cpu_time_seconds" in usage
        assert "max_memory_kb" in usage


class TestApprovalWorkflow:
    """Test plugin approval workflow."""
    
    def test_requires_approval_sandbox_exec(self):
        """Test that sandbox execution requires approval."""
        workflow = PluginApprovalWorkflow()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(sandbox_exec=True),
        )
        context = Mock(spec=PluginContext)
        context.task = {}
        
        assert workflow.requires_approval(manifest, context) is True
    
    def test_requires_approval_network_access(self):
        """Test that network access requires approval."""
        workflow = PluginApprovalWorkflow()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(network_access=True),
        )
        context = Mock(spec=PluginContext)
        context.task = {}
        
        assert workflow.requires_approval(manifest, context) is True
    
    def test_requires_approval_low_risk_workspace_write(self):
        """Test that low-risk workspace write is auto-approved."""
        workflow = PluginApprovalWorkflow(auto_approve_low_risk=True)
        manifest = PluginManifest(
            plugin_id="builtin.test-plugin",
            version="1.0.0",
            plugin_type="generator",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(workspace_write=True),
        )
        context = Mock(spec=PluginContext)
        context.task = {}
        
        # Low risk (builtin plugin, only workspace write)
        assert workflow.requires_approval(manifest, context) is False
    
    def test_calculate_risk_score(self):
        """Test risk score calculation."""
        workflow = PluginApprovalWorkflow()
        
        # High-risk plugin
        high_risk_manifest = PluginManifest(
            plugin_id="external.plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(
                sandbox_exec=True,
                network_access=True,
                workspace_write=True,
            ),
        )
        context = Mock(spec=PluginContext)
        context.task = {}
        
        risk_score = workflow._calculate_risk_score(high_risk_manifest, context)
        assert risk_score == pytest.approx(1.0)  # 0.4 + 0.3 + 0.2 + 0.1 = 1.0
    
    def test_request_approval(self):
        """Test approval request creation."""
        workflow = PluginApprovalWorkflow()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(sandbox_exec=True),
        )
        context = Mock(spec=PluginContext)
        context.task = {
            "taskId": "task-123",
            "traceId": "trace-456",
            "runId": "run-789",
        }
        
        request = workflow.request_approval(manifest, context)
        
        assert isinstance(request, PluginApprovalRequest)
        assert request.plugin_id == "test-plugin"
        assert request.plugin_version == "1.0.0"
        assert request.task_id == "task-123"
        assert request.action == "plugin_execution"
        assert "plugin:execute" in request.required_policies
        assert "plugin:sandbox_exec" in request.required_policies


class TestAuditTrail:
    """Test plugin audit trail."""
    
    def test_audit_event_creation(self):
        """Test audit event creation."""
        event = PluginAuditEvent(
            event_type="plugin_loaded",
            plugin_id="test-plugin",
            plugin_version="1.0.0",
            task_id="task-123",
            trace_id="trace-456",
            run_id="run-789",
            timestamp="2024-01-01T00:00:00Z",
        )
        
        assert event.event_type == "plugin_loaded"
        assert event.plugin_id == "test-plugin"
        assert event.task_id == "task-123"
    
    def test_audit_event_to_dict(self):
        """Test audit event serialization."""
        event = PluginAuditEvent(
            event_type="plugin_loaded",
            plugin_id="test-plugin",
            plugin_version="1.0.0",
            task_id="task-123",
            trace_id="trace-456",
            run_id="run-789",
            timestamp="2024-01-01T00:00:00Z",
            metadata={"key": "value"},
        )
        
        data = event.to_dict()
        assert data["event_type"] == "plugin_loaded"
        assert data["metadata"]["key"] == "value"
        assert "user_id" not in data  # None values removed
    
    def test_log_plugin_loaded(self):
        """Test logging plugin loaded event."""
        audit = PluginAuditTrail()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(),
        )
        
        # Should not raise exception
        audit.log_plugin_loaded(manifest, "task-123", "trace-456", "run-789")
    
    def test_log_plugin_execution_started(self):
        """Test logging plugin execution start."""
        audit = PluginAuditTrail()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(),
        )
        
        # Should not raise exception
        audit.log_plugin_execution_started(manifest, "task-123", "trace-456", "run-789")
    
    def test_log_security_violation(self):
        """Test logging security violation."""
        audit = PluginAuditTrail()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(),
        )
        
        # Should not raise exception
        audit.log_security_violation(
            manifest, "task-123", "trace-456", "run-789",
            "policy_denied", "Plugin not in allowlist"
        )
    
    def test_log_resource_limit_exceeded(self):
        """Test logging resource limit exceeded."""
        audit = PluginAuditTrail()
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(),
        )
        
        # Should not raise exception
        audit.log_resource_limit_exceeded(
            manifest, "task-123", "trace-456", "run-789",
            "memory", "512MB", "600MB"
        )


class TestIntegration:
    """Integration tests for plugin security features."""
    
    def test_end_to_end_plugin_security(self):
        """Test complete plugin security workflow."""
        # Create components
        workflow = PluginApprovalWorkflow()
        audit = PluginAuditTrail()
        manager = PluginIsolationManager()
        
        # Create manifest
        manifest = PluginManifest(
            plugin_id="test-plugin",
            version="1.0.0",
            plugin_type="reviewer",
            entrypoint="test_agent.py",
            class_name="TestAgent",
            permissions=PluginPermissions(workspace_write=True),
        )
        
        # Create context
        context = Mock(spec=PluginContext)
        context.task = {
            "taskId": "task-123",
            "traceId": "trace-456",
            "runId": "run-789",
        }
        
        # Log plugin loaded
        audit.log_plugin_loaded(manifest, "task-123", "trace-456", "run-789")
        
        # Check if approval required (should be False for low-risk)
        requires_approval = workflow.requires_approval(manifest, context)
        assert requires_approval is False
        
        # Log execution start
        audit.log_plugin_execution_started(manifest, "task-123", "trace-456", "run-789")
        
        # Execute with limits
        def plugin_operation():
            return "success"
        
        result = manager.execute_with_limits("test-plugin", plugin_operation)
        assert result == "success"
        
        # Log execution complete
        usage = manager.get_resource_usage()
        audit.log_plugin_execution_completed(
            manifest, "task-123", "trace-456", "run-789",
            resource_usage=usage
        )
