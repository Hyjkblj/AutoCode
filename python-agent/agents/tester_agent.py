from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from plugins.contracts import PluginContext
from plugins.registry import PluginRegistry
from tools.exec_tool import ExecResult, ExecTool
from utils.circuit_breaker import CircuitBreakerOpenError


@dataclass(frozen=True)
class TesterResult:
    success: bool
    attempts: int
    retries: int
    command: str
    status: str
    reason: str | None
    trace_id: str | None
    run_id: str | None


class TesterAgent:
    def __init__(
        self,
        exec_tool: ExecTool | None = None,
        max_retries: int = 3,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        self.exec_tool = exec_tool or ExecTool()
        self.max_retries = max(0, min(max_retries, 3))
        self.plugin_registry = plugin_registry or PluginRegistry()

    def execute(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> TesterResult:
        prompt = str(task.get("prompt", "")).strip()
        command = self._resolve_test_command(task, client, plan, publish_event)
        last_result: ExecResult | None = None
        last_error: Exception | None = None

        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            publish_event(
                {
                    "stage": "TesterAgent",
                    "message": "Running validation command.",
                    "planName": plan.plan_name,
                    "attempt": attempt,
                    "maxAttempts": total_attempts,
                    "command": command,
                },
            )
            try:
                result = self.exec_tool.execute(task, command, prompt=prompt, intent="test")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt <= self.max_retries:
                    publish_event(
                        {
                            "stage": "TesterAgent",
                            "message": "Validation command failed to dispatch, retrying.",
                            "attempt": attempt,
                            "error": str(exc),
                        },
                    )
                    continue
                publish_event(
                    {
                        "stage": "TesterAgent",
                        "message": "Validation command dispatch failed.",
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                return TesterResult(
                    success=False,
                    attempts=attempt,
                    retries=attempt - 1,
                    command=command,
                    status="sandbox_request_failed",
                    reason=str(exc),
                    trace_id=None,
                    run_id=None,
                )

            last_result = result
            if result.ok:
                publish_event(
                    {
                        "stage": "TesterAgent",
                        "message": "Validation passed.",
                        "attempt": attempt,
                        "status": result.status,
                        "exitCode": result.exit_code,
                        "traceId": result.trace_id,
                        "runId": result.run_id,
                    },
                )
                return TesterResult(
                    success=True,
                    attempts=attempt,
                    retries=attempt - 1,
                    command=command,
                    status=result.status,
                    reason=result.reason,
                    trace_id=result.trace_id,
                    run_id=result.run_id,
                )

            if attempt <= self.max_retries:
                publish_event(
                    {
                        "stage": "TesterAgent",
                        "message": "Validation failed, retrying.",
                        "attempt": attempt,
                        "status": result.status,
                        "reason": result.reason,
                    },
                )
                continue

            publish_event(
                {
                    "stage": "TesterAgent",
                    "message": "Validation failed after retries.",
                    "attempt": attempt,
                    "status": result.status,
                    "reason": result.reason,
                    "traceId": result.trace_id,
                    "runId": result.run_id,
                },
            )
            return TesterResult(
                success=False,
                attempts=attempt,
                retries=attempt - 1,
                command=command,
                status=result.status,
                reason=result.reason,
                trace_id=result.trace_id,
                run_id=result.run_id,
            )

        if last_result is not None:
            return TesterResult(
                success=False,
                attempts=total_attempts,
                retries=self.max_retries,
                command=command,
                status=last_result.status,
                reason=last_result.reason,
                trace_id=last_result.trace_id,
                run_id=last_result.run_id,
            )
        return TesterResult(
            success=False,
            attempts=total_attempts,
            retries=self.max_retries,
            command=command,
            status="sandbox_request_failed",
            reason=str(last_error) if last_error else "sandbox_request_failed",
            trace_id=None,
            run_id=None,
        )

    def _resolve_test_command(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> str:
        explicit = str(task.get("testCommand", "")).strip()
        if explicit:
            return explicit

        task.setdefault("intent", "test")
        plugin_context = PluginContext(task=task, client=client, plan=plan, publish_event=publish_event)
        plugins = self.plugin_registry.resolve_tester_plugins(plugin_context)
        for plugin in plugins:
            manifest = plugin.manifest
            task["_activeTesterPlugin"] = manifest.plugin_id
            breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
            publish_event(
                {
                    "stage": "TesterPlugin",
                    "message": "Executing tester plugin.",
                    "pluginId": manifest.plugin_id,
                    "pluginVersion": manifest.version,
                    "breakerStatus": breaker_state.get("status"),
                    "failureCount": breaker_state.get("failureCount"),
                    "permissions": {
                        "workspaceRead": manifest.permissions.workspace_read,
                        "workspaceWrite": manifest.permissions.workspace_write,
                        "sandboxExec": manifest.permissions.sandbox_exec,
                        "networkAccess": manifest.permissions.network_access,
                    },
                }
            )
            try:
                command = str(
                    self.plugin_registry.execute_plugin(
                        manifest.plugin_id,
                        lambda: plugin.resolve_command(plugin_context),
                    )
                ).strip()
                if command:
                    task["testCommand"] = command
                    return command
            except CircuitBreakerOpenError:
                breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
                publish_event(
                    {
                        "stage": "TesterPlugin",
                        "message": "Plugin skipped due to circuit breaker, falling back to built-in implementation.",
                        "pluginId": manifest.plugin_id,
                        "breakerStatus": breaker_state.get("status"),
                        "failureCount": breaker_state.get("failureCount"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
                publish_event(
                    {
                        "stage": "TesterPlugin",
                        "message": "Tester plugin failed, falling back to built-in command resolution.",
                        "pluginId": manifest.plugin_id,
                        "breakerStatus": breaker_state.get("status"),
                        "failureCount": breaker_state.get("failureCount"),
                        "error": str(exc),
                    }
                )
        task.pop("_activeTesterPlugin", None)
        return _resolve_test_command(task)


class EventPublisher:
    def __call__(self, payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        raise NotImplementedError


def _resolve_test_command(task: dict[str, Any]) -> str:
    explicit = str(task.get("testCommand", "")).strip()
    if explicit:
        return explicit
    env_command = os.getenv("MVP_TEST_COMMAND", "").strip()
    if env_command:
        return env_command
    return "echo test_from_python_agent"

