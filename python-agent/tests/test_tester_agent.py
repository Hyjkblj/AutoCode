from __future__ import annotations

from typing import Any

from agents.planner_agent import PlanResult
from agents.tester_agent import TesterAgent as AgentTester
from plugins.contracts import PluginManifest, PluginPermissions
from plugins.runtime import PluginRuntimeManager
from tools.exec_tool import ExecResult


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


class _TesterPluginRegistryStub:
    def __init__(self, plugin, *, failure_threshold: int = 1) -> None:  # noqa: ANN001
        self.plugin = plugin
        self.runtime = PluginRuntimeManager(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=30.0,
        )

    def resolve_tester_plugins(self, context):  # noqa: ANN001
        return [self.plugin]

    def execute_plugin(self, plugin_id: str, operation):  # noqa: ANN001
        return self.runtime.execute(plugin_id, operation)

    def plugin_state(self, plugin_id: str) -> dict[str, object]:
        return self.runtime.state(plugin_id)


class _FailingTesterPlugin:
    def __init__(self) -> None:
        self.manifest = PluginManifest(
            plugin_id="test.failing-tester",
            version="0.1.0",
            plugin_type="tester",
            entrypoint="",
            class_name="FailingTesterPlugin",
            permissions=PluginPermissions(),
        )
        self.calls = 0

    def supports(self, context) -> bool:  # noqa: ANN001
        return True

    def resolve_command(self, context) -> str:  # noqa: ANN001
        self.calls += 1
        raise RuntimeError("tester exploded")


class _SequenceExecTool:
    def __init__(self, results: list[ExecResult]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def execute(self, task: dict[str, Any], command: str, *, prompt: str = "", intent: str = "test") -> ExecResult:
        self.calls.append({"task": task, "command": command, "prompt": prompt, "intent": intent})
        if not self.results:
            raise RuntimeError("no more fake results")
        return self.results.pop(0)


def test_tester_agent_retries_then_succeeds() -> None:
    exec_tool = _SequenceExecTool(
        [
            ExecResult(
                ok=False,
                status="failed",
                exit_code=1,
                output="fail_1",
                retryable=True,
                reason="test_failed",
                tool="command.exec",
                tool_version="1.0.0",
                trace_id="trc_1",
                run_id="run_1",
                approval_id=None,
            ),
            ExecResult(
                ok=False,
                status="failed",
                exit_code=1,
                output="fail_2",
                retryable=True,
                reason="test_failed",
                tool="command.exec",
                tool_version="1.0.0",
                trace_id="trc_2",
                run_id="run_2",
                approval_id=None,
            ),
            ExecResult(
                ok=True,
                status="ok",
                exit_code=0,
                output="pass",
                retryable=False,
                reason=None,
                tool="command.exec",
                tool_version="1.0.0",
                trace_id="trc_3",
                run_id="run_3",
                approval_id=None,
            ),
        ]
    )
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = AgentTester(exec_tool=exec_tool, max_retries=3).execute(
        task={"taskId": "task_401", "prompt": "run tests"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["test"]),
        publish_event=publish,
    )

    assert result.success is True
    assert result.attempts == 3
    assert result.retries == 2
    assert len(exec_tool.calls) == 3
    assert all(call["intent"] == "test" for call in exec_tool.calls)


def test_tester_agent_stops_after_max_retries() -> None:
    failing = ExecResult(
        ok=False,
        status="failed",
        exit_code=1,
        output="still failing",
        retryable=True,
        reason="test_failed",
        tool="command.exec",
        tool_version="1.0.0",
        trace_id="trc_fail",
        run_id="run_fail",
        approval_id=None,
    )
    exec_tool = _SequenceExecTool([failing, failing, failing, failing])
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = AgentTester(exec_tool=exec_tool, max_retries=3).execute(
        task={"taskId": "task_402", "prompt": "run tests"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["test"]),
        publish_event=publish,
    )

    assert result.success is False
    assert result.attempts == 4
    assert result.retries == 3
    assert len(exec_tool.calls) == 4
    assert events[-1][1]["message"] == "Validation failed after retries."


def test_tester_agent_uses_tester_plugin_for_backend_target() -> None:
    exec_tool = _SequenceExecTool(
        [
            ExecResult(
                ok=True,
                status="ok",
                exit_code=0,
                output="pass",
                retryable=False,
                reason=None,
                tool="command.exec",
                tool_version="1.0.0",
                trace_id="trc_plugin_test",
                run_id="run_plugin_test",
                approval_id=None,
            ),
        ]
    )
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    result = AgentTester(exec_tool=exec_tool, max_retries=1).execute(
        task={"taskId": "task_403", "prompt": "run backend tests", "_generated_target": "backend"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="test_pipeline", steps=["test"]),
        publish_event=publish,
    )

    assert result.success is True
    assert exec_tool.calls[0]["command"] == "pytest -q"
    plugin_events = [payload for event_type, payload in events if event_type == "ASSISTANT_OUTPUT" and payload.get("stage") == "TesterPlugin"]
    assert plugin_events
    assert plugin_events[0]["pluginId"] == "builtin.backend-pytest-tester"


def test_tester_agent_skips_open_tester_plugin_and_falls_back() -> None:
    plugin = _FailingTesterPlugin()
    registry = _TesterPluginRegistryStub(plugin)
    exec_tool = _SequenceExecTool(
        [
            ExecResult(
                ok=True,
                status="ok",
                exit_code=0,
                output="pass",
                retryable=False,
                reason=None,
                tool="command.exec",
                tool_version="1.0.0",
                trace_id="trc_plugin_skip",
                run_id="run_plugin_skip",
                approval_id=None,
            ),
            ExecResult(
                ok=True,
                status="ok",
                exit_code=0,
                output="pass",
                retryable=False,
                reason=None,
                tool="command.exec",
                tool_version="1.0.0",
                trace_id="trc_plugin_skip_2",
                run_id="run_plugin_skip_2",
                approval_id=None,
            ),
        ]
    )
    agent = AgentTester(exec_tool=exec_tool, max_retries=0, plugin_registry=registry)
    first_events: list[tuple[str, dict[str, Any]]] = []
    second_events: list[tuple[str, dict[str, Any]]] = []

    def publish_first(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        first_events.append((event_type, payload))

    def publish_second(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        second_events.append((event_type, payload))

    first_result = agent.execute(
        task={"taskId": "task_404", "prompt": "run tests"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="test_pipeline", steps=["test"]),
        publish_event=publish_first,
    )
    second_result = agent.execute(
        task={"taskId": "task_405", "prompt": "run tests"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="test_pipeline", steps=["test"]),
        publish_event=publish_second,
    )

    assert first_result.success is True
    assert second_result.success is True
    assert plugin.calls == 1
    assert exec_tool.calls[0]["command"] == "echo test_from_python_agent"
    assert exec_tool.calls[1]["command"] == "echo test_from_python_agent"
    first_failure_events = [
        payload
        for event_type, payload in first_events
        if event_type == "ASSISTANT_OUTPUT"
        and payload.get("message") == "Tester plugin failed, falling back to built-in command resolution."
    ]
    second_skip_events = [
        payload
        for event_type, payload in second_events
        if event_type == "ASSISTANT_OUTPUT"
        and payload.get("message") == "Plugin skipped due to circuit breaker, falling back to built-in implementation."
    ]
    assert first_failure_events
    assert first_failure_events[0]["breakerStatus"] == "open"
    assert first_failure_events[0]["failureCount"] == 1
    assert second_skip_events
    assert second_skip_events[0]["breakerStatus"] == "open"
    assert second_skip_events[0]["failureCount"] == 1
