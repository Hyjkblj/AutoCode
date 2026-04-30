from __future__ import annotations

import zipfile
from typing import Any

from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from agents.reviewer_agent import ReviewResult
from agents.tester_agent import TesterResult as RunResult
from llm.llm_client import LLMClient
from memory.redis_memory import RedisMemory
from orchestrator.agent_orchestrator import AgentOrchestrator, _error_code_from_reason, _resolve_fix_loop_max_attempts
from plugins.contracts import PluginManifest, PluginPermissions
from plugins.runtime import PluginRuntimeManager
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


class _RaisingExecTool:
    def __init__(self, message: str) -> None:
        self.message = message
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
        raise RuntimeError(self.message)


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


class _SequenceTesterAgent:
    def __init__(self, results: list[RunResult]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def execute(self, task, client, plan, publish_event):  # noqa: ANN001
        self.calls.append({"task": task, "plan": plan.plan_name})
        if not self.results:
            raise RuntimeError("no more tester results")
        result = self.results.pop(0)
        publish_event(
            {
                "stage": "TesterAgent",
                "message": "Validation completed.",
                "status": result.status,
                "attempts": result.attempts,
            }
        )
        return result


class _FakeCoderAgent:
    def execute(self, task, client, plan, publish_event):  # noqa: ANN001
        publish_event({"stage": "CoderAgent", "message": "Mock coder run."})
        return True


class _InvalidReviewerAgent:
    def review(self, task, client, plan, publish_event):  # noqa: ANN001
        publish_event({"stage": "ReviewerAgent", "message": "Invalid reviewer payload."})
        return {"approved": True}


class _ReviewerPluginRegistryStub:
    def __init__(self, plugin, *, failure_threshold: int = 1) -> None:  # noqa: ANN001
        self.plugin = plugin
        self.runtime = PluginRuntimeManager(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=30.0,
        )

    def resolve_reviewer_plugins(self, context):  # noqa: ANN001
        return [self.plugin]

    def execute_plugin(self, plugin_id: str, operation):  # noqa: ANN001
        return self.runtime.execute(plugin_id, operation)

    def plugin_state(self, plugin_id: str) -> dict[str, object]:
        return self.runtime.state(plugin_id)


class _FailingReviewerPlugin:
    def __init__(self) -> None:
        self.manifest = PluginManifest(
            plugin_id="test.failing-reviewer",
            version="0.1.0",
            plugin_type="reviewer",
            entrypoint="",
            class_name="FailingReviewerPlugin",
            permissions=PluginPermissions(),
        )
        self.calls = 0

    def supports(self, context) -> bool:  # noqa: ANN001
        return True

    def review(self, context) -> ReviewResult:  # noqa: ANN001
        self.calls += 1
        raise RuntimeError("reviewer exploded")


class _FailingDagScheduler:
    def run(self, nodes):  # noqa: ANN001
        raise RuntimeError("dag exploded")


def _metric_value(
    metrics: list[dict[str, Any]],
    name: str,
    *,
    stage: str,
    status: str | None = None,
) -> Any:
    for item in metrics:
        if item.get("name") != name:
            continue
        tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
        if tags.get("stage") != stage:
            continue
        if status is not None and tags.get("status") != status:
            continue
        return item.get("value")
    return None


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


def test_orchestrator_marks_task_failed_when_llm_key_missing(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    task = {
        "taskId": "task_100b",
        "assistant": "ai-agent",
        "sessionKey": "sess_100b",
        "prompt": "analyze this change",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["ASSISTANT_OUTPUT", "ASSISTANT_OUTPUT", "TASK_FAILED"]
    assert client.events[2][1]["payload"]["reason"] == "llm_key_missing"
    assert client.events[2][1]["payload"]["errorCode"] == "LLM_KEY_MISSING"
    assert client.events[2][1]["payload"]["planName"] == "blocked_missing_key"
    assert "ANTHROPIC_API_KEY" in client.events[2][1]["payload"]["detail"]


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


def test_orchestrator_marks_code_change_failed_when_fix_loop_exhausted(monkeypatch, tmp_path) -> None:
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
    assert client.events[-1][1]["payload"]["reason"] == "fix_loop_exhausted"
    assert client.events[-1][1]["payload"]["errorCode"] == "FIX_LOOP_EXHAUSTED"
    assert client.events[-1][1]["payload"]["attempt"] == 3
    assert client.events[-1][1]["payload"]["maxAttempts"] == 3
    assert len(tester.calls) == 4


def test_orchestrator_marks_task_done_when_fix_loop_recovers(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("TODO: patch me\n", encoding="utf-8")
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_105",
        "assistant": "ai-agent",
        "sessionKey": "sess_105",
        "prompt": "fix readme and implement update",
        "workspacePath": str(workspace),
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _SequenceTesterAgent(
        [
            RunResult(
                success=False,
                attempts=1,
                retries=0,
                command="echo test",
                status="failed",
                reason="test_failed",
                trace_id="trc_task_105_1",
                run_id="run_task_105_1",
            ),
            RunResult(
                success=True,
                attempts=1,
                retries=0,
                command="echo test",
                status="ok",
                reason=None,
                trace_id="trc_task_105_2",
                run_id="run_task_105_2",
            ),
        ]
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types[-1] == "TASK_DONE"
    assert client.events[-1][1]["payload"]["attempt"] == 1
    assert client.events[-1][1]["payload"]["maxAttempts"] == 3
    assert len(tester.calls) == 2
    fix_loop_events = [
        event["payload"]
        for _, event in client.events
        if event["type"] == "ASSISTANT_OUTPUT" and event["payload"].get("message") == "Fix loop attempt started."
    ]
    assert fix_loop_events


def test_orchestrator_marks_code_change_failed_when_fix_loop_max_attempt_is_one(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "1")
    monkeypatch.setattr(LLMClient, "chat", lambda self, messages: "Updated docs\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("TODO: patch me\n", encoding="utf-8")
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_105b",
        "assistant": "ai-agent",
        "sessionKey": "sess_105b",
        "prompt": "fix readme and implement update",
        "workspacePath": str(workspace),
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="review passed", issues=[]))
    tester = _FakeTesterAgent(
        RunResult(
            success=False,
            attempts=1,
            retries=0,
            command="echo test",
            status="failed",
            reason="test_failed",
            trace_id="trc_task_105b",
            run_id="run_task_105b",
        )
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types[-1] == "TASK_FAILED"
    assert client.events[-1][1]["payload"]["reason"] == "fix_loop_exhausted"
    assert client.events[-1][1]["payload"]["attempt"] == 1
    assert client.events[-1][1]["payload"]["maxAttempts"] == 1
    assert len(tester.calls) == 2


def test_orchestrator_marks_review_rejected_with_error_code(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    task = {
        "taskId": "task_108",
        "assistant": "ai-agent",
        "sessionKey": "sess_108",
        "prompt": "fix code issue",
    }
    client = _FakeClient()
    reviewer = _FakeReviewerAgent(
        ReviewResult(approved=False, summary="unsafe operation", issues=["dangerous shell"], risk_level="high")
    )
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_108",
            run_id="run_task_108",
        )
    )

    orchestrator = AgentOrchestrator(
        coder_agent=_FakeCoderAgent(),
        reviewer_agent=reviewer,
        tester_agent=tester,
    )
    orchestrator.handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types[-1] == "TASK_FAILED"
    assert client.events[-1][1]["payload"]["reason"] == "review_rejected"
    assert client.events[-1][1]["payload"]["errorCode"] == "REVIEW_REJECTED"
    assert client.events[-1][1]["payload"]["riskLevel"] == "high"


def test_orchestrator_marks_parallel_result_invalid_with_error_code(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    task = {
        "taskId": "task_109",
        "assistant": "ai-agent",
        "sessionKey": "sess_109",
        "prompt": "fix code issue",
    }
    client = _FakeClient()
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_109",
            run_id="run_task_109",
        )
    )
    orchestrator = AgentOrchestrator(
        coder_agent=_FakeCoderAgent(),
        reviewer_agent=_InvalidReviewerAgent(),
        tester_agent=tester,
    )
    orchestrator.handle_task(task, client)

    assert client.events[-1][1]["type"] == "TASK_FAILED"
    assert client.events[-1][1]["payload"]["reason"] == "parallel_result_invalid"
    assert client.events[-1][1]["payload"]["errorCode"] == "PARALLEL_RESULT_INVALID"


def test_orchestrator_marks_parallel_pipeline_error_with_error_code(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    task = {
        "taskId": "task_110",
        "assistant": "ai-agent",
        "sessionKey": "sess_110",
        "prompt": "fix code issue",
    }
    client = _FakeClient()
    orchestrator = AgentOrchestrator(
        coder_agent=_FakeCoderAgent(),
        dag_scheduler=_FailingDagScheduler(),
    )
    orchestrator.handle_task(task, client)

    assert client.events[-1][1]["type"] == "TASK_FAILED"
    assert client.events[-1][1]["payload"]["reason"] == "parallel_pipeline_error"
    assert client.events[-1][1]["payload"]["errorCode"] == "PARALLEL_PIPELINE_ERROR"


def test_orchestrator_marks_sandbox_request_failed_with_error_code(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def _raise(*_args, **_kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(LLMClient, "chat", _raise)

    task = {
        "taskId": "task_111",
        "assistant": "ai-agent",
        "sessionKey": "sess_111",
        "prompt": "please deploy this service",
    }
    client = _FakeClient()
    orchestrator = AgentOrchestrator(exec_tool=_RaisingExecTool("sandbox down"))
    orchestrator.handle_task(task, client)

    assert client.events[-1][1]["type"] == "TASK_FAILED"
    assert client.events[-1][1]["payload"]["reason"] == "sandbox_request_failed"
    assert client.events[-1][1]["payload"]["errorCode"] == "SANDBOX_REQUEST_FAILED"


def test_orchestrator_handles_flask_health_task_end_to_end_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    app_file = workspace / "app.py"
    app_file.write_text(
        'from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "ok"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    def _chat(self, messages):  # noqa: ANN001
        system_prompt = str(messages[0].get("content", ""))
        if "intent classifier" in system_prompt:
            return '{"intent":"code_change","confidence":0.97,"reason":"flask health endpoint request"}'
        if "planning agent" in system_prompt:
            return '{"plan_name":"code_change_pipeline","steps":["update flask routes","run tests"]}'
        if "coding assistant" in system_prompt:
            return (
                "from flask import Flask\n\n"
                "app = Flask(__name__)\n\n"
                '@app.route("/")\n'
                "def index():\n"
                '    return "ok"\n\n'
                '@app.route("/health")\n'
                "def health():\n"
                '    return {"status": "ok"}, 200\n'
            )
        if "code reviewer" in system_prompt:
            return '{"risk_level":"low","issues":[],"summary":"safe endpoint addition"}'
        raise AssertionError(f"unexpected LLM call: {system_prompt}")

    monkeypatch.setattr(LLMClient, "chat", _chat)

    task = {
        "taskId": "task_106",
        "assistant": "ai-agent",
        "sessionKey": "sess_106",
        "prompt": "add /health endpoint to Flask app",
        "workspacePath": str(workspace),
        "testCommand": "pytest -q",
    }
    client = _FakeClient()
    exec_tool = _FakeExecTool(
        ExecResult(
            ok=True,
            status="ok",
            exit_code=0,
            output="tests passed",
            retryable=False,
            reason=None,
            tool="test.execute",
            tool_version="1.0.0",
            trace_id="trc_task_106",
            run_id="run_task_106",
            approval_id=None,
        )
    )

    AgentOrchestrator(exec_tool=exec_tool).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert "FILE_PATCH_PREVIEW" in types
    assert types[-1] == "TASK_DONE"
    assert client.events[0][1]["payload"]["intent"] == "code_change"
    patch_event = [event for _, event in client.events if event["type"] == "FILE_PATCH_PREVIEW"][0]
    assert "---" in patch_event["payload"]["patch"]
    assert "+++" in patch_event["payload"]["patch"]
    assert "/health" in patch_event["payload"]["patch"]
    assert '@app.route("/health")' in app_file.read_text(encoding="utf-8")
    assert exec_tool.calls[0]["intent"] == "test"
    assert client.events[-1][1]["payload"]["result"] == "coded_reviewed_tested"


def test_orchestrator_flask_health_task_enters_fix_loop_when_test_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    app_file = workspace / "app.py"
    app_file.write_text(
        'from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "ok"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    coder_call_count = {"value": 0}

    def _chat(self, messages):  # noqa: ANN001
        system_prompt = str(messages[0].get("content", ""))
        if "intent classifier" in system_prompt:
            return '{"intent":"code_change","confidence":0.95,"reason":"flask route change"}'
        if "planning agent" in system_prompt:
            return '{"plan_name":"code_change_pipeline","steps":["edit flask app","run tests"]}'
        if "coding assistant" in system_prompt:
            coder_call_count["value"] += 1
            if coder_call_count["value"] == 1:
                return (
                    "from flask import Flask\n\n"
                    "app = Flask(__name__)\n\n"
                    '@app.route("/")\n'
                    "def index():\n"
                    '    return "ok"\n\n'
                    '@app.route("/health")\n'
                    "def health():\n"
                    '    return {"status": "ok"}, 200\n'
                )
            return (
                "from flask import Flask\n\n"
                "app = Flask(__name__)\n\n"
                '@app.route("/")\n'
                "def index():\n"
                '    return "ok"\n\n'
                '@app.route("/health")\n'
                "def health():\n"
                '    return {"status": "ok", "fixLoop": True}, 200\n'
            )
        if "code reviewer" in system_prompt:
            return '{"risk_level":"low","issues":[],"summary":"safe endpoint addition"}'
        raise AssertionError(f"unexpected LLM call: {system_prompt}")

    monkeypatch.setattr(LLMClient, "chat", _chat)

    task = {
        "taskId": "task_107",
        "assistant": "ai-agent",
        "sessionKey": "sess_107",
        "prompt": "add /health endpoint to Flask app",
        "workspacePath": str(workspace),
    }
    client = _FakeClient()
    tester = _SequenceTesterAgent(
        [
            RunResult(
                success=False,
                attempts=1,
                retries=0,
                command="pytest -q",
                status="failed",
                reason="assert 404 == 200",
                trace_id="trc_task_107_1",
                run_id="run_task_107_1",
            ),
            RunResult(
                success=True,
                attempts=1,
                retries=0,
                command="pytest -q",
                status="ok",
                reason=None,
                trace_id="trc_task_107_2",
                run_id="run_task_107_2",
            ),
        ]
    )

    AgentOrchestrator(tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types[-1] == "TASK_DONE"
    assert len(tester.calls) == 2
    fix_loop_events = [
        event["payload"]
        for _, event in client.events
        if event["type"] == "ASSISTANT_OUTPUT" and event["payload"].get("message") == "Fix loop attempt started."
    ]
    assert fix_loop_events
    assert client.events[-1][1]["payload"]["attempt"] == 1
    assert client.events[-1][1]["payload"]["maxAttempts"] == 3


def test_orchestrator_publishes_artifact_ready_for_web_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
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
    monkeypatch.delenv("ARK_API_KEY", raising=False)
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
    assert client.events[4][1]["payload"]["errorCode"] == "APPROVAL_REJECTED"


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


def test_orchestrator_publishes_artifact_ready_for_web_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(workspace))

    task = {
        "taskId": "task_105w",
        "assistant": "ai-agent",
        "sessionKey": "sess_105w",
        "prompt": "build a simple web page",
        "workspacePath": str(workspace),
        "target": "web",
        "templateId": "product",
        "exportMode": "zip",
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
            trace_id="trc_task_105w",
            run_id="run_task_105w",
        )
    )

    AgentOrchestrator(reviewer_agent=reviewer, tester_agent=tester).handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert "SPEC_PROPOSED" in types
    assert "BUILD_STARTED" in types
    assert "BUILD_LOG" in types
    assert "BUILD_DONE" in types
    assert "ARTIFACT_READY" in types
    assert types[-1] == "TASK_DONE"

    spec_event = [event for _, event in client.events if event["type"] == "SPEC_PROPOSED"][0]
    spec_payload = spec_event["payload"]
    assert spec_payload["target"] == "web"
    assert spec_payload["templateId"] == "product"
    assert spec_payload["exportMode"] == "zip"
    assert spec_payload["path"] == "spec.json"
    assert spec_payload["schemaVersion"] == "v1"
    assert spec_payload["artifact"]["type"] == "spec"
    assert spec_payload["artifact"]["artifactId"].startswith("art_spec_task_105w")

    build_started_event = [event for _, event in client.events if event["type"] == "BUILD_STARTED"][0]
    build_started_payload = build_started_event["payload"]
    assert build_started_payload["buildId"] == "build_task_105w_web"
    assert build_started_payload["tool"] == "artifact.export.zip"
    assert build_started_payload["target"] == "web"
    assert build_started_payload["traceId"] == "trc_task_105w"
    assert build_started_payload["runId"] == "run_task_105w"

    build_log_event = [event for _, event in client.events if event["type"] == "BUILD_LOG"][0]
    build_log_payload = build_log_event["payload"]
    assert build_log_payload["buildId"] == "build_task_105w_web"
    assert build_log_payload["level"] == "info"
    assert build_log_payload["message"] == "Packaging generated web files into export.zip artifact."
    assert build_log_payload["traceId"] == "trc_task_105w"
    assert build_log_payload["runId"] == "run_task_105w"

    build_done_event = [event for _, event in client.events if event["type"] == "BUILD_DONE"][0]
    build_done_payload = build_done_event["payload"]
    assert build_done_payload["buildId"] == "build_task_105w_web"
    assert build_done_payload["status"] == "success"
    assert isinstance(build_done_payload["durationMs"], int)
    assert build_done_payload["durationMs"] >= 0
    assert build_done_payload["traceId"] == "trc_task_105w"
    assert build_done_payload["runId"] == "run_task_105w"

    spec_index = types.index("SPEC_PROPOSED")
    build_started_index = types.index("BUILD_STARTED")
    build_log_index = types.index("BUILD_LOG")
    build_done_index = types.index("BUILD_DONE")
    artifact_ready_index = types.index("ARTIFACT_READY")
    assert spec_index < build_started_index < build_log_index < build_done_index < artifact_ready_index

    ready_event = [event for _, event in client.events if event["type"] == "ARTIFACT_READY"][0]
    artifact = ready_event["payload"]["artifact"]
    assert artifact["artifactId"] == "art_uploaded_001"
    assert artifact["type"] == "zip"
    assert artifact["name"] == "export.zip"
    assert artifact["entryPath"] == "index.html"
    assert artifact["run"]["command"] == "python -m http.server 8000"
    assert artifact["run"]["hints"] == [
        "Run the command in the extracted artifact directory.",
        "Open http://localhost:8000/index.html in a browser.",
    ]
    assert ready_event["payload"]["target"] == "web"
    assert ready_event["payload"]["templateId"] == "product"
    assert ready_event["payload"]["exportMode"] == "zip"

    assert client.upload_calls
    zip_path = client.upload_calls[0]["filePath"]
    with zipfile.ZipFile(zip_path, "r") as zipf:
        names = sorted(zipf.namelist())
    assert names == ["README.generated.md", "app.js", "index.html", "styles.css"]


def test_orchestrator_rejects_unsupported_target(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_106t",
        "assistant": "ai-agent",
        "sessionKey": "sess_106t",
        "prompt": "generate miniapp",
        "target": "miniapp",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["TASK_FAILED"]
    assert client.events[0][1]["payload"]["reason"] == "unsupported_target"
    assert client.events[0][1]["payload"]["errorCode"] == "UNSUPPORTED_TARGET"


def test_orchestrator_rejects_unsupported_export_mode(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_106x",
        "assistant": "ai-agent",
        "sessionKey": "sess_106x",
        "prompt": "build web app",
        "target": "web",
        "exportMode": "tar",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    types = [event["type"] for _, event in client.events]
    assert types == ["TASK_FAILED"]
    assert client.events[0][1]["payload"]["reason"] == "unsupported_export_mode"
    assert client.events[0][1]["payload"]["errorCode"] == "UNSUPPORTED_EXPORT_MODE"


def test_resolve_fix_loop_max_attempts_bounds(monkeypatch) -> None:
    monkeypatch.delenv("MVP_FIX_LOOP_MAX_ATTEMPTS", raising=False)
    assert _resolve_fix_loop_max_attempts() == 3

    monkeypatch.setenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "abc")
    assert _resolve_fix_loop_max_attempts() == 3

    monkeypatch.setenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "10")
    assert _resolve_fix_loop_max_attempts() == 3

    monkeypatch.setenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "0")
    assert _resolve_fix_loop_max_attempts() == 1

    monkeypatch.setenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "-5")
    assert _resolve_fix_loop_max_attempts() == 1


def test_error_code_from_reason_normalization() -> None:
    assert _error_code_from_reason("approval rejected") == "APPROVAL_REJECTED"
    assert _error_code_from_reason("fix-loop_exhausted") == "FIX_LOOP_EXHAUSTED"
    assert _error_code_from_reason("  ") == "UNKNOWN_ERROR"


def test_orchestrator_terminal_payload_contains_observability_summary(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_obs_001",
        "assistant": "ai-agent",
        "sessionKey": "sess_obs_001",
        "prompt": "please analyze this change",
    }
    client = _FakeClient()

    AgentOrchestrator().handle_task(task, client)

    terminal_payload = client.events[-1][1]["payload"]
    observability = terminal_payload["observability"]
    assert observability["engine"] == "legacy"
    assert observability["taskStatus"] == "done"
    assert observability["intent"] == "analyze"
    assert observability["traceId"].startswith("trc_task_obs_001_")
    assert observability["runId"].startswith("run_task_obs_001_")
    span_names = {item["name"] for item in observability["spans"]}
    assert {"memory_context", "intent_inference", "plan_build"} <= span_names
    metric_names = {item["name"] for item in observability["metrics"]}
    assert "task_total" in metric_names
    assert "event_publish_total" in metric_names


def test_orchestrator_observability_reports_llm_cache_hits_per_stage(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def provider(backend, messages, model, temperature):  # noqa: ANN001
        system_prompt = messages[0]["content"]
        if "intent classifier" in system_prompt:
            return '{"intent":"analyze","confidence":0.91,"reason":"cached"}'
        if "planning agent" in system_prompt:
            return '{"plan_name":"analysis_pipeline","steps":["gather context","report next actions"]}'
        raise AssertionError(f"unexpected llm messages: {messages}")

    shared_client = LLMClient(
        response_provider=provider,
        cache_enabled=True,
        cache_max_size=8,
        cache_ttl_seconds=60.0,
    )
    shared_client.clear_cache(reset_stats=True)
    orchestrator = AgentOrchestrator(
        intent_agent=IntentAgent(llm_client=shared_client),
        planner_agent=PlannerAgent(llm_client=shared_client),
    )

    warmup_task = {
        "taskId": "task_cache_obs_001",
        "assistant": "ai-agent",
        "sessionKey": "sess_cache_obs_001",
        "prompt": "please analyze this change",
    }
    cached_task = {
        "taskId": "task_cache_obs_002",
        "assistant": "ai-agent",
        "sessionKey": "sess_cache_obs_002",
        "prompt": "please analyze this change",
    }
    warmup_client = _FakeClient()
    cached_client = _FakeClient()

    orchestrator.handle_task(warmup_task, warmup_client)
    orchestrator.handle_task(cached_task, cached_client)

    metrics = cached_client.events[-1][1]["payload"]["observability"]["metrics"]
    assert _metric_value(metrics, "llm_cache_requests_total", stage="IntentAgent") == 1
    assert _metric_value(metrics, "llm_cache_hits_total", stage="IntentAgent") == 1
    assert _metric_value(metrics, "llm_cache_event_total", stage="IntentAgent", status="hit") == 1
    assert _metric_value(metrics, "llm_cache_requests_total", stage="PlannerAgent") == 1
    assert _metric_value(metrics, "llm_cache_hits_total", stage="PlannerAgent") == 1
    assert _metric_value(metrics, "llm_cache_event_total", stage="PlannerAgent", status="hit") == 1


def test_orchestrator_langgraph_engine_routes_analyze_via_runtime(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_lg_001",
        "assistant": "ai-agent",
        "sessionKey": "sess_lg_001",
        "prompt": "please analyze this change",
    }
    client = _FakeClient()

    AgentOrchestrator(engine="langgraph").handle_task(task, client)

    runtime_events = [
        event["payload"]
        for _, event in client.events
        if event["type"] == "ASSISTANT_OUTPUT" and event["payload"].get("stage") == "LangGraphRuntime"
    ]
    assert runtime_events
    assert runtime_events[0]["intent"] == "analyze"
    terminal_payload = client.events[-1][1]["payload"]
    assert terminal_payload["executionPath"] == "langgraph"
    assert terminal_payload["observability"]["engine"] == "langgraph"
    assert terminal_payload["observability"]["intent"] == "analyze"


def test_orchestrator_langgraph_engine_routes_test_without_exec_tool(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    task = {
        "taskId": "task_lg_002",
        "assistant": "ai-agent",
        "sessionKey": "sess_lg_002",
        "prompt": "run tests for this project",
    }
    client = _FakeClient()
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="pytest -q",
            status="ok",
            reason=None,
            trace_id="trc_task_lg_002",
            run_id="run_task_lg_002",
        )
    )

    AgentOrchestrator(
        engine="langgraph",
        tester_agent=tester,
        exec_tool=_RaisingExecTool("legacy exec tool should not be used"),
    ).handle_task(task, client)

    assert tester.calls
    stages = [event["payload"].get("stage") for _, event in client.events if event["type"] == "ASSISTANT_OUTPUT"]
    assert "ExecTool" not in stages
    terminal_payload = client.events[-1][1]["payload"]
    assert terminal_payload["executionPath"] == "langgraph"
    assert terminal_payload["command"] == "pytest -q"
    assert terminal_payload["observability"]["engine"] == "langgraph"
    assert terminal_payload["observability"]["intent"] == "test"


def test_orchestrator_uses_reviewer_plugin_before_builtin_reviewer(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    task = {
        "taskId": "task_plugin_review_001",
        "assistant": "ai-agent",
        "sessionKey": "sess_plugin_review_001",
        "prompt": "fix code issue",
        "latestDiff": "--- a/x\n+++ b/x\n+rm -rf /\n",
    }
    client = _FakeClient()
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_plugin_review_001",
            run_id="run_task_plugin_review_001",
        )
    )

    orchestrator = AgentOrchestrator(
        coder_agent=_FakeCoderAgent(),
        tester_agent=tester,
    )
    orchestrator.handle_task(task, client)

    assert client.events[-1][1]["type"] == "TASK_FAILED"
    plugin_events = [
        event["payload"]
        for _, event in client.events
        if event["type"] == "ASSISTANT_OUTPUT" and event["payload"].get("stage") == "ReviewerPlugin"
    ]
    assert plugin_events
    assert plugin_events[0]["pluginId"] == "builtin.diff-risk-reviewer"
    assert client.events[-1][1]["payload"]["reason"] == "review_rejected"


def test_orchestrator_skips_open_reviewer_plugin_and_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    plugin = _FailingReviewerPlugin()
    registry = _ReviewerPluginRegistryStub(plugin)
    reviewer = _FakeReviewerAgent(ReviewResult(approved=True, summary="builtin reviewer fallback", issues=[]))
    tester = _FakeTesterAgent(
        RunResult(
            success=True,
            attempts=1,
            retries=0,
            command="echo test",
            status="ok",
            reason=None,
            trace_id="trc_task_plugin_skip",
            run_id="run_task_plugin_skip",
        )
    )
    orchestrator = AgentOrchestrator(
        coder_agent=_FakeCoderAgent(),
        reviewer_agent=reviewer,
        tester_agent=tester,
        plugin_registry=registry,
    )

    first_task = {
        "taskId": "task_plugin_skip_001",
        "assistant": "ai-agent",
        "sessionKey": "sess_plugin_skip_001",
        "prompt": "fix code issue",
        "latestDiff": "--- a/x\n+++ b/x\n+safe change\n",
    }
    second_task = {
        "taskId": "task_plugin_skip_002",
        "assistant": "ai-agent",
        "sessionKey": "sess_plugin_skip_002",
        "prompt": "fix code issue again",
        "latestDiff": "--- a/x\n+++ b/x\n+safe change 2\n",
    }
    first_client = _FakeClient()
    second_client = _FakeClient()

    orchestrator.handle_task(first_task, first_client)
    orchestrator.handle_task(second_task, second_client)

    assert plugin.calls == 1
    assert len(reviewer.calls) == 2
    first_failure_events = [
        event["payload"]
        for _, event in first_client.events
        if event["type"] == "ASSISTANT_OUTPUT"
        and event["payload"].get("message") == "Reviewer plugin failed, falling back to built-in reviewer."
    ]
    second_skip_events = [
        event["payload"]
        for _, event in second_client.events
        if event["type"] == "ASSISTANT_OUTPUT"
        and event["payload"].get("message") == "Plugin skipped due to circuit breaker, falling back to built-in implementation."
    ]
    assert first_failure_events
    assert first_failure_events[0]["breakerStatus"] == "open"
    assert first_failure_events[0]["failureCount"] == 1
    assert second_skip_events
    assert second_skip_events[0]["breakerStatus"] == "open"
    assert second_skip_events[0]["failureCount"] == 1
