from __future__ import annotations

import zipfile
from typing import Any

from agents.reviewer_agent import ReviewResult
from agents.tester_agent import TesterResult as RunResult
from memory.redis_memory import RedisMemory
from orchestrator.agent_orchestrator import AgentOrchestrator
from tools.exec_tool import ExecResult


class _FakeClient:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.upload_calls: list[dict[str, Any]] = []

    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append((task_id, event))
        return {"eventId": event.get("eventId")}

    def upload_artifact(
        self,
        task_id: str,
        file_path: str,
        *,
        name: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        self.upload_calls.append(
            {
                "taskId": task_id,
                "filePath": file_path,
                "name": name,
                "contentType": content_type,
            }
        )
        return {
            "artifactId": "art_uploaded_001",
            "name": name or "export.zip",
            "contentType": content_type or "application/zip",
            "sizeBytes": 1024,
            "sha256": "a" * 64,
        }


class _FakeExecTool:
    def __init__(self, result: ExecResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def execute(self, task: dict[str, Any], command: str, *, prompt: str = "", intent: str = "deploy") -> ExecResult:
        self.calls.append(
            {
                "task": task,
                "command": command,
                "prompt": prompt,
                "intent": intent,
            }
        )
        return self.result


class _FakeReviewerAgent:
    def __init__(self, result: ReviewResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def review(self, task, client, plan, publish_event):  # noqa: ANN001
        self.calls.append({"task": task, "plan": plan.plan_name})
        publish_event(
            {
                "stage": "ReviewerAgent",
                "message": "Code review completed.",
                "approved": self.result.approved,
                "summary": self.result.summary,
            }
        )
        return self.result


class _FakeTesterAgent:
    def __init__(self, result: RunResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def execute(self, task, client, plan, publish_event):  # noqa: ANN001
        self.calls.append({"task": task, "plan": plan.plan_name})
        publish_event(
            {
                "stage": "TesterAgent",
                "message": "Validation completed.",
                "status": self.result.status,
                "attempts": self.result.attempts,
            }
        )
        return self.result


def test_orchestrator_emits_intent_and_planner_events(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_100",
        "assistant": "ai-agent",
        "sessionKey": "sess_100",
        "prompt": "please analyze this change",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "TASK_DONE"]
    assert client.events[0][1]["payload"]["stage"] == "IntentAgent"
    assert client.events[1][1]["payload"]["stage"] == "PlannerAgent"


def test_orchestrator_routes_code_change_to_coder_and_emits_patch_preview(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("TODO: patch me\n", encoding="utf-8")
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_101",
        "assistant": "ai-agent",
        "sessionKey": "sess_101",
        "prompt": "fix readme and implement update",
        "workspacePath": str(workspace),
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_101",
            run_id="run_task_101",
        )
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types[0:5] == ["ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "FILE_PATCH_PREVIEW", "ASSISTANT_OUTPUT"]
    assert types[-1] == "TASK_DONE"
    assert types.count("ASSISTANT_OUTPUT") == 6
    assert client.events[3][1]["payload"]["files"] == [{"path": "README.md", "changeType": "modify"}]
    assert client.events[-1][1]["payload"]["result"] == "coded_reviewed_tested"
    stages = [event["payload"].get("stage") for _, event in client.events if event["type"] == "ASSISTANT_OUTPUT"]
    assert "Orchestrator" in stages
    assert "ReviewerAgent" in stages
    assert "TesterAgent" in stages
    assert reviewer.calls[0]["plan"] == "code_change_pipeline"
    assert tester.calls[0]["plan"] == "code_change_pipeline"


def test_orchestrator_marks_code_change_failed_when_tests_fail(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("TODO: patch me\n", encoding="utf-8")
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_104",
        "assistant": "ai-agent",
        "sessionKey": "sess_104",
        "prompt": "fix readme and implement update",
        "workspacePath": str(workspace),
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _FakeTesterAgent(
        RunResult(
            success=False,
            attempts=4,
            retries=3,
            command="echo test",
            status="failed",
            reason="test_failed",
            trace_id="trc_task_104",
            run_id="run_task_104",
        )
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types[-1] == "TASK_FAILED"
    assert client.events[-1][1]["payload"]["reason"] == "test_failed"
    assert client.events[-1][1]["payload"]["attempts"] == 4


def test_orchestrator_publishes_artifact_ready_for_web_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_105",
        "assistant": "ai-agent",
        "sessionKey": "sess_105",
        "prompt": "生成一个基础web页面",
        "workspacePath": str(workspace),
        "target": "web",
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_105",
            run_id="run_task_105",
        )
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert "ARTIFACT_READY" in types
    assert types[-1] == "TASK_DONE"
    ready_event = [event for _, event in client.events if event["type"] == "ARTIFACT_READY"][0]
    artifact = ready_event["payload"]["artifact"]
    assert artifact["artifactId"] == "art_uploaded_001"
    assert artifact["type"] == "zip"
    assert artifact["name"] == "export.zip"

    assert client.upload_calls
    zip_path = client.upload_calls[0]["filePath"]
    with zipfile.ZipFile(zip_path, "r") as zipf:
        names = sorted(zipf.namelist())
    assert names == ["README.generated.md", "app.js", "index.html", "styles.css"]


def test_orchestrator_publishes_artifact_when_assistant_web_without_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_105b",
        "assistant": "web",
        "sessionKey": "sess_105b",
        "prompt": "请帮我生成一个待办应用",
        "workspacePath": str(workspace),
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_105b",
            run_id="run_task_105b",
        )
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert "ARTIFACT_READY" in types
    assert types[-1] == "TASK_DONE"
    ready_event = [event for _, event in client.events if event["type"] == "ARTIFACT_READY"][0]
    artifact = ready_event["payload"]["artifact"]
    assert artifact["type"] == "zip"
    assert artifact["name"] == "export.zip"
    assert client.upload_calls


def test_orchestrator_rejects_unsupported_target(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_106",
        "assistant": "ai-agent",
        "sessionKey": "sess_106",
        "prompt": "generate miniapp",
        "target": "miniapp",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["TASK_FAILED"]
    assert client.events[0][1]["payload"]["reason"] == "unsupported_target"


def test_orchestrator_routes_deploy_to_exec_tool_and_marks_task_done(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    exec_tool = _FakeExecTool(
        ExecResult(
            ok=True,
            status="ok",
            exit_code=0,
            output="deploy ok",
            retryable=False,
            reason=None,
            tool="deploy.execute",
            tool_version="1.0.0",
            trace_id="trc_task_102",
            run_id="run_task_102",
            approval_id=None,
        )
    )
    task = {
        "taskId": "task_102",
        "assistant": "ai-agent",
        "sessionKey": "sess_102",
        "prompt": "please deploy this service",
        "workspacePath": "D:/workspace/demo",
    }
    client = _FakeClient()

    AgentOrchestrator(exec_tool=exec_tool).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "TASK_DONE"]
    assert exec_tool.calls[0]["intent"] == "deploy"
    assert client.events[4][1]["payload"]["result"] == "executed"
    assert client.events[4][1]["payload"]["tool"] == "deploy.execute"
    assert client.events[4][1]["payload"]["traceId"] == "trc_task_102"


def test_orchestrator_marks_task_failed_when_exec_tool_returns_failure(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    exec_tool = _FakeExecTool(
        ExecResult(
            ok=False,
            status="approval_rejected",
            exit_code=None,
            output="",
            retryable=False,
            reason="approval_rejected",
            tool="deploy.execute",
            tool_version="1.0.0",
            trace_id="trc_task_103",
            run_id="run_task_103",
            approval_id="apr_1",
        )
    )
    task = {
        "taskId": "task_103",
        "assistant": "ai-agent",
        "sessionKey": "sess_103",
        "prompt": "please deploy now",
        "command": "echo deploy_now",
    }
    client = _FakeClient()

    AgentOrchestrator(exec_tool=exec_tool).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "TASK_FAILED"]
    assert exec_tool.calls[0]["command"] == "echo deploy_now"
    assert client.events[4][1]["payload"]["reason"] == "approval_rejected"


def test_orchestrator_reuses_memory_context_for_second_code_change(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("TODO: patch me\n", encoding="utf-8")
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    class _MemoryAwareTester:
        def __init__(self) -> None:
            self.seen_test_commands: list[str] = []

        def execute(self, task, client, plan, publish_event):  # noqa: ANN001
            test_command = str(task.get("testCommand", "")).strip()
            self.seen_test_commands.append(test_command)
            publish_event({"stage": "TesterAgent", "message": "Validation completed.", "status": "ok", "attempts": 1})
            return RunResult(
                success=True,
                attempts=1,
                retries=0,
                command=test_command or "echo test_from_python_agent",
                status="ok",
                reason=None,
                trace_id="trc_memory",
                run_id="run_memory",
            )

    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _MemoryAwareTester()
    memory = RedisMemory(backend="memory", namespace="test:memory:reuse")
    orchestrator = AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester, memory_store=memory)

    task_one = {
        "taskId": "task_201",
        "assistant": "ai-agent",
        "sessionKey": "sess_201",
        "prompt": "fix readme and implement update",
        "workspacePath": str(workspace),
        "testCommand": "echo first_test_command",
    }
    client_one = _FakeClient()
    orchestrator.handle_task(task_one, client_one)

    task_two = {
        "taskId": "task_202",
        "assistant": "ai-agent",
        "sessionKey": "sess_202",
        "prompt": "fix readme again",
        "workspacePath": str(workspace),
    }
    client_two = _FakeClient()
    orchestrator.handle_task(task_two, client_two)

    assert tester.seen_test_commands[0] == "echo first_test_command"
    assert tester.seen_test_commands[1] == "echo first_test_command"
    memory_events = [
        event["payload"]
        for _, event in client_two.events
        if event["type"] == "ASSISTANT_OUTPUT" and event["payload"].get("stage") == "Memory"
    ]
    assert memory_events
    assert memory_events[0]["lastTestCommand"] == "echo first_test_command"
