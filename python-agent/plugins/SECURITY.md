# Plugin Security Implementation

## Overview

This document describes the comprehensive security enhancements implemented for the AutoCode plugin system as part of task 34.1 (Backend Upgrade 2.0 - P2-2 phase).

## Implemented Features

### 1. Plugin Whitelisting and Capability-Based Security

**Location:** `plugins/loader.py`, `plugins/registry.py`

**Features:**
- **Deny-by-default policy**: Plugins must be explicitly allowlisted to execute
- **Multi-level allowlisting**: Support for global, environment-specific, and project-specific allowlists
- **Capability-based permissions**: Fine-grained control over plugin capabilities
  - `workspace_read`: Read files from workspace (default: allowed)
  - `workspace_write`: Write files to workspace (default: denied)
  - `sandbox_exec`: Execute code in sandbox (default: denied)
  - `network_access`: Make network requests (default: denied)

**Configuration:**
```json
{
  "default_deny": true,
  "global_allow": ["builtin.diff-risk-reviewer"],
  "environment_allow": {
    "staging": ["*"]
  },
  "project_allow": {
    "demo-project": ["builtin.backend-template-generator"]
  },
  "capability_policy": {
    "allow_workspace_write": true,
    "allow_sandbox_exec": false,
    "allow_network_access": false
  }
}
```

### 2. Resource Limits and Isolation

**Location:** `plugins/resource_limits.py`

**Features:**
- **Memory limits**: Maximum 512 MB per plugin (configurable)
- **CPU time limits**: Maximum 30 seconds CPU time (configurable)
- **Wall time limits**: Maximum 60 seconds execution time (configurable)
- **File descriptor limits**: Maximum 100 file descriptors (configurable)
- **Process limits**: Maximum 10 processes (configurable)
- **Thread-based isolation**: Plugins execute in separate threads with timeout enforcement
- **Resource usage tracking**: Detailed resource consumption metrics

**Environment Variables:**
- `MVP_PLUGIN_MAX_MEMORY_MB`: Maximum memory per plugin (default: 512)
- `MVP_PLUGIN_MAX_CPU_TIME_SECONDS`: Maximum CPU time (default: 30)
- `MVP_PLUGIN_MAX_WALL_TIME_SECONDS`: Maximum wall time (default: 60)
- `MVP_PLUGIN_MAX_FILE_DESCRIPTORS`: Maximum file descriptors (default: 100)
- `MVP_PLUGIN_MAX_PROCESSES`: Maximum processes (default: 10)

**Platform Support:**
- Unix/Linux: Full resource limit enforcement using `resource` module
- Windows: Wall time enforcement only (resource module not available)

### 3. Approval Workflow

**Location:** `plugins/approval_workflow.py`

**Features:**
- **Risk-based approval**: Automatic approval for low-risk operations, manual approval for high-risk
- **Risk scoring algorithm**:
  - Sandbox execution: +0.4
  - Network access: +0.3
  - Workspace write: +0.2
  - Non-builtin plugin: +0.1
- **Approval request creation**: Structured approval requests with context and justification
- **Integration with Approval Service**: Submits approval requests to centralized approval service
- **RBAC policy enforcement**: Required policies based on plugin permissions

**Risk Thresholds:**
- Risk score < 0.5: Auto-approved (if enabled)
- Risk score ≥ 0.5: Requires manual approval
- Sandbox execution or network access: Always requires approval

**Approval Request Structure:**
```python
{
  "approvalId": "uuid",
  "taskId": "task-123",
  "traceId": "trace-456",
  "runId": "run-789",
  "action": "plugin_execution",
  "tool": "plugin:plugin-id",
  "reason": "Human-readable justification",
  "riskScore": 0.7,
  "context": {
    "plugin_id": "...",
    "plugin_version": "...",
    "permissions": {...}
  },
  "requiredPolicies": ["plugin:execute", "plugin:sandbox_exec"],
  "timeoutSeconds": 300
}
```

### 4. Comprehensive Audit Trail

**Location:** `plugins/audit_trail.py`

**Features:**
- **Structured audit events**: JSON-formatted audit logs with consistent schema
- **Complete lifecycle tracking**: Logs all plugin operations from loading to completion
- **Security violation logging**: Tracks policy denials and capability violations
- **Resource usage logging**: Records resource consumption for each execution
- **Circuit breaker events**: Logs circuit breaker state changes

**Audit Event Types:**
- `plugin_loaded`: Plugin discovered and loaded
- `plugin_execution_started`: Plugin execution begins
- `plugin_execution_completed`: Plugin execution succeeds
- `plugin_execution_failed`: Plugin execution fails
- `plugin_approval_requested`: Approval requested for high-risk operation
- `plugin_approval_decision`: Approval granted or denied
- `plugin_security_violation`: Security policy violation detected
- `plugin_resource_limit_exceeded`: Resource limit exceeded
- `plugin_circuit_breaker_opened`: Circuit breaker opened due to failures

**Audit Event Schema:**
```json
{
  "event_type": "plugin_execution_completed",
  "plugin_id": "builtin.backend-generator",
  "plugin_version": "1.0.0",
  "task_id": "task-123",
  "trace_id": "trace-456",
  "run_id": "run-789",
  "timestamp": "2024-01-01T00:00:00Z",
  "resource_usage": {
    "user_cpu_time_seconds": 1.5,
    "system_cpu_time_seconds": 0.3,
    "max_memory_kb": 102400
  }
}
```

### 5. Enhanced Plugin Runtime

**Location:** `plugins/runtime.py`

**Features:**
- **Integrated security controls**: Combines circuit breaker, resource limits, and audit trail
- **Automatic failure handling**: Circuit breaker protection with configurable thresholds
- **Resource monitoring**: Tracks and reports resource usage for each plugin
- **Security violation detection**: Detects and logs security policy violations

**Circuit Breaker Configuration:**
- `MVP_PLUGIN_BREAKER_FAILURE_THRESHOLD`: Failures before opening (default: 3)
- `MVP_PLUGIN_BREAKER_RECOVERY_SECONDS`: Recovery timeout (default: 30)

### 6. Enhanced Plugin Registry

**Location:** `plugins/registry.py`

**Features:**
- **Security-aware plugin resolution**: Checks policies and capabilities before loading
- **Approval workflow integration**: Requests approval for high-risk operations
- **Comprehensive audit logging**: Logs all plugin operations and security events
- **Backward compatibility**: Maintains existing plugin API while adding security features

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Plugin Request                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Plugin Registry (registry.py)                  │
│  • Policy check (allowlist)                                 │
│  • Capability check (permissions)                           │
│  • Audit logging (plugin loaded)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         Approval Workflow (approval_workflow.py)            │
│  • Risk score calculation                                   │
│  • Approval request (if high-risk)                          │
│  • Audit logging (approval requested)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│          Plugin Runtime (runtime.py)                        │
│  • Circuit breaker check                                    │
│  • Resource limit enforcement                               │
│  • Audit logging (execution start/complete/failed)          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│      Resource Isolation (resource_limits.py)                │
│  • Thread-based isolation                                   │
│  • Timeout enforcement                                      │
│  • Resource usage tracking                                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Plugin Execution                           │
└─────────────────────────────────────────────────────────────┘
```

## Testing

**Location:** `tests/test_plugin_security.py`

**Test Coverage:**
- Resource limits and isolation (5 tests)
- Approval workflow (5 tests)
- Audit trail (6 tests)
- End-to-end integration (1 test)

**Total:** 17 tests, all passing

## Requirements Validation

This implementation validates the following requirements:

- **Requirement 13.1** (Security Policy Enforcement): Plugin whitelisting, capability-based security, resource limits
- **Requirement 13.2** (RBAC Implementation): Approval workflow with policy-based access control
- **Requirement 13.3** (Audit Trail Completeness): Comprehensive audit logging for all plugin operations
- **Requirement 13.6** (Security Incident Response): Security violation detection and logging

## Usage Examples

### Basic Plugin Execution with Security

```python
from plugins.registry import PluginRegistry
from plugins.contracts import PluginContext

# Create registry with security features
registry = PluginRegistry()

# Create plugin context
context = PluginContext(
    task={"taskId": "task-123", "traceId": "trace-456", "runId": "run-789"},
    client=control_plane_client,
    plan=plan_result,
    publish_event=event_publisher,
)

# Resolve plugins (with security checks)
reviewer_plugins = registry.resolve_reviewer_plugins(context)

# Execute plugin (with approval workflow and resource limits)
for plugin in reviewer_plugins:
    try:
        result = registry.execute_plugin_with_context(
            plugin_id=plugin.manifest.plugin_id,
            manifest=plugin.manifest,
            context=context,
            operation=lambda: plugin.review(context),
        )
    except RuntimeError as e:
        if "requires approval" in str(e):
            # Handle approval required
            print(f"Approval required: {e}")
        else:
            raise
```

### Custom Resource Limits

```python
from plugins.resource_limits import ResourceLimits, PluginIsolationManager

# Create custom resource limits
limits = ResourceLimits(
    max_memory_mb=256,
    max_cpu_time_seconds=15,
    max_wall_time_seconds=30,
)

# Create isolation manager
manager = PluginIsolationManager(limits)

# Execute with custom limits
result = manager.execute_with_limits(
    plugin_id="my-plugin",
    operation=lambda: my_plugin_function(),
    timeout_seconds=20,
)
```

### Approval Workflow

```python
from plugins.approval_workflow import PluginApprovalWorkflow

# Create approval workflow
workflow = PluginApprovalWorkflow(
    client=control_plane_client,
    auto_approve_low_risk=True,
    risk_threshold=0.5,
)

# Check if approval required
if workflow.requires_approval(manifest, context):
    # Request approval
    request = workflow.request_approval(manifest, context)
    approval_id = workflow.submit_approval_request(request)
    
    # Wait for approval decision
    decision = workflow.check_approval_status(approval_id)
    if decision.decision == "APPROVED":
        # Execute plugin
        pass
```

## Future Enhancements

1. **Async approval workflow**: Non-blocking approval requests with callbacks
2. **Plugin sandboxing**: OS-level sandboxing using containers or VMs
3. **Network policy enforcement**: Fine-grained network access control
4. **Plugin signing**: Cryptographic verification of plugin integrity
5. **Rate limiting**: Per-plugin rate limits to prevent abuse
6. **Resource quotas**: Per-user or per-project resource quotas
7. **Audit log export**: Export audit logs to external systems (SIEM, etc.)
8. **Real-time monitoring**: Dashboard for plugin security metrics

## References

- Design Document: `.kiro/specs/backend-upgrade-2.0/design.md`
- Requirements Document: `.kiro/specs/backend-upgrade-2.0/requirements.md`
- Tasks Document: `.kiro/specs/backend-upgrade-2.0/tasks.md`
- Plugin README: `python-agent/plugins/README.md`
