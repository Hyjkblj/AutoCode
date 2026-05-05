from __future__ import annotations

import json

import pytest

from agents.planner_agent import PlanResult
from plugins.loader import PluginLoader
from plugins.registry import PluginRegistry
from plugins.runtime import PluginRuntimeManager


class _DummyClient:
    pass


def _publish(_payload, event_type: str = "ASSISTANT_OUTPUT") -> None:
    return None


def test_plugin_loader_loads_allowlisted_reviewer_plugin() -> None:
    loader = PluginLoader()

    plugins = loader.load_reviewer_plugins()

    assert len(plugins) == 1
    assert plugins[0].manifest.plugin_id == "builtin.diff-risk-reviewer"
    assert plugins[0].manifest.permissions.workspace_write is False


def test_plugin_loader_loads_allowlisted_generator_plugin() -> None:
    loader = PluginLoader()

    plugins = loader.load_generator_plugins()

    assert len(plugins) == 1
    assert plugins[0].manifest.plugin_id == "builtin.backend-template-generator"
    assert plugins[0].manifest.permissions.workspace_write is True


def test_plugin_loader_loads_allowlisted_tester_plugin() -> None:
    loader = PluginLoader()

    plugins = loader.load_tester_plugins()

    assert len(plugins) == 1
    assert plugins[0].manifest.plugin_id == "builtin.backend-pytest-tester"
    assert plugins[0].manifest.permissions.workspace_write is False


def test_plugin_loader_reads_scoped_policy(tmp_path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "default_deny": True,
                "global_allow": ["builtin.diff-risk-reviewer"],
                "environment_allow": {"prod": ["builtin.backend-pytest-tester"]},
                "project_allow": {"project-a": ["builtin.backend-template-generator"]},
                "capability_policy": {
                    "allow_workspace_write": True,
                    "allow_sandbox_exec": False,
                    "allow_network_access": False,
                },
            }
        ),
        encoding="utf-8",
    )
    loader = PluginLoader(allowlist_file=allowlist)

    policy = loader.read_policy()

    assert policy.is_allowed("builtin.diff-risk-reviewer", environment="dev", project_id="x") is True
    assert policy.is_allowed("builtin.backend-pytest-tester", environment="prod", project_id="x") is True
    assert policy.is_allowed("builtin.backend-template-generator", environment="dev", project_id="project-a") is True
    assert policy.is_allowed("builtin.backend-template-generator", environment="dev", project_id="other") is False
    assert policy.capability_policy.allow_workspace_write is True
    assert policy.capability_policy.allow_sandbox_exec is False


def test_plugin_registry_resolves_reviewer_for_code_change() -> None:
    registry = PluginRegistry()
    from plugins.contracts import PluginContext

    context = PluginContext(
        task={
            "taskId": "task_plugin_001",
            "assistant": "ai-agent",
            "intent": "code_change",
            "latestDiff": "--- a/a\n+++ b/a\n+danger\n",
        },
        client=_DummyClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=_publish,
    )

    plugins = registry.resolve_reviewer_plugins(context)

    assert len(plugins) == 1
    assert plugins[0].manifest.plugin_id == "builtin.diff-risk-reviewer"


def test_plugin_registry_filters_plugins_by_environment_policy(tmp_path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "default_deny": True,
                "global_allow": [],
                "environment_allow": {"staging": ["builtin.diff-risk-reviewer"]},
                "project_allow": {},
            }
        ),
        encoding="utf-8",
    )
    registry = PluginRegistry(loader=PluginLoader(allowlist_file=allowlist))

    from plugins.contracts import PluginContext

    allowed = PluginContext(
        task={
            "taskId": "task_plugin_env_001",
            "assistant": "ai-agent",
            "intent": "code_change",
            "environment": "staging",
            "latestDiff": "--- a/a\n+++ b/a\n+danger\n",
        },
        client=_DummyClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=_publish,
    )
    denied = PluginContext(
        task={
            "taskId": "task_plugin_env_002",
            "assistant": "ai-agent",
            "intent": "code_change",
            "environment": "prod",
            "latestDiff": "--- a/a\n+++ b/a\n+danger\n",
        },
        client=_DummyClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["review"]),
        publish_event=_publish,
    )

    assert len(registry.resolve_reviewer_plugins(allowed)) == 1
    assert registry.resolve_reviewer_plugins(denied) == []


def test_plugin_registry_resolves_generator_for_backend_target() -> None:
    registry = PluginRegistry()
    from plugins.contracts import PluginContext

    context = PluginContext(
        task={
            "taskId": "task_plugin_002",
            "assistant": "ai-agent",
            "intent": "code_change",
            "target": "backend",
            "_requestedGenerationTarget": "backend",
            "prompt": "build a todo backend",
        },
        client=_DummyClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["generate"]),
        publish_event=_publish,
    )

    plugins = registry.resolve_generator_plugins(context, target="backend")

    assert len(plugins) == 1
    assert plugins[0].manifest.plugin_id == "builtin.backend-template-generator"


def test_plugin_registry_resolves_tester_for_backend_target() -> None:
    registry = PluginRegistry()
    from plugins.contracts import PluginContext

    context = PluginContext(
        task={
            "taskId": "task_plugin_003",
            "assistant": "ai-agent",
            "intent": "test",
            "_generated_target": "backend",
            "prompt": "validate generated backend",
        },
        client=_DummyClient(),
        plan=PlanResult(plan_name="test_pipeline", steps=["test"]),
        publish_event=_publish,
    )

    plugins = registry.resolve_tester_plugins(context)

    assert len(plugins) == 1
    assert plugins[0].manifest.plugin_id == "builtin.backend-pytest-tester"


def test_plugin_registry_filters_plugins_by_capability_policy(tmp_path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "default_deny": True,
                "global_allow": ["builtin.backend-template-generator"],
                "environment_allow": {},
                "project_allow": {},
                "capability_policy": {
                    "allow_workspace_write": False,
                    "allow_sandbox_exec": False,
                    "allow_network_access": False,
                },
            }
        ),
        encoding="utf-8",
    )
    registry = PluginRegistry(loader=PluginLoader(allowlist_file=allowlist))

    from plugins.contracts import PluginContext

    context = PluginContext(
        task={
            "taskId": "task_plugin_cap_001",
            "assistant": "ai-agent",
            "intent": "code_change",
            "target": "backend",
            "_requestedGenerationTarget": "backend",
            "prompt": "build a todo backend",
        },
        client=_DummyClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["generate"]),
        publish_event=_publish,
    )

    plugins = registry.resolve_generator_plugins(context, target="backend")

    assert plugins == []


def test_plugin_runtime_manager_opens_breaker_after_consecutive_failures() -> None:
    runtime = PluginRuntimeManager(failure_threshold=2, recovery_timeout_seconds=30.0)

    with pytest.raises(RuntimeError, match="boom_1"):
        runtime.execute("demo.plugin", lambda: (_ for _ in ()).throw(RuntimeError("boom_1")))
    state = runtime.state("demo.plugin")
    assert state["status"] == "closed"
    assert state["failureCount"] == 1

    with pytest.raises(RuntimeError, match="boom_2"):
        runtime.execute("demo.plugin", lambda: (_ for _ in ()).throw(RuntimeError("boom_2")))
    state = runtime.state("demo.plugin")
    assert state["status"] == "open"
    assert state["failureCount"] == 2

    with pytest.raises(RuntimeError, match="circuit breaker open"):
        runtime.execute("demo.plugin", lambda: "never called")
    state = runtime.state("demo.plugin")
    assert state["status"] == "open"
    assert state["failureCount"] == 2


def test_plugin_runtime_manager_resets_failure_count_after_success() -> None:
    runtime = PluginRuntimeManager(failure_threshold=2, recovery_timeout_seconds=1.0)

    with pytest.raises(RuntimeError):
        runtime.execute("demo.plugin", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    result = runtime.execute("demo.plugin", lambda: "ok")
    state = runtime.state("demo.plugin")

    assert result == "ok"
    assert state["status"] == "closed"
    assert state["failureCount"] == 0


def test_plugin_registry_exposes_runtime_state() -> None:
    registry = PluginRegistry(runtime_manager=PluginRuntimeManager(failure_threshold=2, recovery_timeout_seconds=5.0))

    state = registry.plugin_state("builtin.backend-template-generator")

    assert state["pluginId"] == "builtin.backend-template-generator"
    assert state["status"] == "closed"
    assert state["failureThreshold"] == 2
    assert state["recoveryTimeoutSeconds"] == 5.0


def test_plugin_loader_rejects_entrypoint_outside_plugin_dir(tmp_path) -> None:
    manifest = tmp_path / "escape_agent.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "plugin_id": "test.escape-plugin",
                "version": "0.1.0",
                "plugin_type": "reviewer",
                "entrypoint": "..\\outside_agent.py",
                "class_name": "EscapePlugin",
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )
    loader = PluginLoader(plugin_dir=tmp_path)

    with pytest.raises(PermissionError, match="escapes plugin directory"):
        loader.load_reviewer_plugins()
