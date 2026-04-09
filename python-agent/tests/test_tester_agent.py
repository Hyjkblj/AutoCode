from __future__ import annotations

from typing import Any

from agents.planner_agent import PlanResult
from agents.tester_agent import TesterAgent as AgentTester
from tools.exec_tool import ExecResult


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


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
