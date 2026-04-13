from __future__ import annotations

from typing import Any

from agents.coder_agent import CoderAgent
from llm.llm_client import LLMClient
from agents.planner_agent import PlanResult
from tools.file_tool import FileTool
from utils.web_template import WebTemplateGenerator


class _FakeClient:
    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": event.get("eventId"), "taskId": task_id}


def test_coder_agent_emits_file_patch_preview(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "README.md"
    target.write_text("TODO: update docs\n", encoding="utf-8")

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(workspace)]))
    ok = coder.execute(
        task={"workspacePath": str(workspace), "prompt": "fix readme text"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is True
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "FILE_PATCH_PREVIEW"]
    assert events[1][1]["files"] == [{"path": "README.md", "changeType": "modify"}]
    assert "---" in events[1][1]["patch"]
    assert "coder-agent-note" in target.read_text(encoding="utf-8")


def test_coder_agent_reports_task_failed_when_write_is_out_of_bounds(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    denied_prefix = tmp_path / "allowed"
    workspace.mkdir(parents=True, exist_ok=True)

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(denied_prefix)]))
    ok = coder.execute(
        task={"workspacePath": str(workspace), "prompt": "implement feature"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is False
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "TASK_FAILED"]
    assert events[1][1]["reason"] == "path_not_allowed"


def test_coder_agent_generates_web_template_files(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    task = {"workspacePath": str(workspace), "prompt": "build a landing page", "target": "web"}
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(workspace)]))
    ok = coder.execute(
        task=task,
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["generate", "package"]),
        publish_event=publish,
    )

    assert ok is True
    assert (workspace / "index.html").exists()
    assert (workspace / "styles.css").exists()
    assert (workspace / "app.js").exists()
    assert (workspace / "README.generated.md").exists()
    assert task["_generated_files"] == ["index.html", "styles.css", "app.js", "README.generated.md"]
    assert any(item[0] == "FILE_PATCH_PREVIEW" for item in events)


def test_coder_agent_web_generation_falls_back_when_llm_errors(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def broken_provider(backend, messages, model, temperature):  # noqa: ANN001
        raise RuntimeError("model timeout")

    generator = WebTemplateGenerator(llm_client=LLMClient(response_provider=broken_provider))
    coder = CoderAgent(file_tool=FileTool([str(workspace)]), web_template_generator=generator)
    task = {"workspacePath": str(workspace), "prompt": "build a dashboard", "target": "web"}
    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    ok = coder.execute(
        task=task,
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["generate", "package"]),
        publish_event=publish,
    )

    assert ok is True
    assert task["_llm_fallback"] is True
    assert str(task["_llm_generation_reason"]).startswith("llm_fallback:")
    assert any(item[0] == "FILE_PATCH_PREVIEW" for item in events)


def test_coder_agent_falls_back_to_allowed_workspace_prefix_when_missing(tmp_path, monkeypatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MVP_ALLOWED_WORKSPACE_PREFIXES", str(allowed))

    events: list[tuple[str, dict[str, Any]]] = []

    def publish(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        events.append((event_type, payload))

    coder = CoderAgent(file_tool=FileTool([str(allowed)]))
    ok = coder.execute(
        task={"workspacePath": "None", "prompt": "add note"},
        client=_FakeClient(),
        plan=PlanResult(plan_name="code_change_pipeline", steps=["read", "patch"]),
        publish_event=publish,
    )

    assert ok is True
    assert [item[0] for item in events] == ["ASSISTANT_OUTPUT", "FILE_PATCH_PREVIEW"]
    assert (allowed / "AGENT_PATCH_PREVIEW.md").exists()


def test_coder_agent_generate_gate_is_not_triggered_by_generic_prompt() -> None:
    should_generate = CoderAgent._should_generate_project(
        target="",
        assistant="ai-agent",
        prompt="implement login validation and update tests",
    )
    assert should_generate is False


def test_coder_agent_generate_gate_prefers_explicit_web_target() -> None:
    should_generate = CoderAgent._should_generate_project(
        target="web",
        assistant="ai-agent",
        prompt="refactor docs and config",
    )
    assert should_generate is True
