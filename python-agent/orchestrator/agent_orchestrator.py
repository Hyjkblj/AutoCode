from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from agents.coder_agent import CoderAgent
from agents.intent_agent import IntentAgent, IntentDecision
from agents.planner_agent import PlanResult, PlannerAgent
from agents.reviewer_agent import ReviewResult, ReviewerAgent
from agents.tester_agent import TesterAgent, TesterResult
from client.control_plane_client import ControlPlaneClient
from memory.redis_memory import RedisMemory
from orchestrator.dag_scheduler import DagNode, DagScheduler
from tools.exec_tool import ExecResult, ExecTool
from utils.artifact_utils import ArtifactBundle, build_export_zip


class AgentOrchestrator(BaseAgent):
    def __init__(
        self,
        intent_agent: IntentAgent | None = None,
        planner_agent: PlannerAgent | None = None,
        coder_agent: CoderAgent | None = None,
        reviewer_agent: ReviewerAgent | None = None,
        tester_agent: TesterAgent | None = None,
        exec_tool: ExecTool | None = None,
        memory_store: RedisMemory | None = None,
        dag_scheduler: DagScheduler | None = None,
    ) -> None:
        super().__init__()
        resolved_exec_tool = exec_tool or ExecTool()
        self.intent_agent = intent_agent or IntentAgent()
        self.planner_agent = planner_agent or PlannerAgent()
        self.coder_agent = coder_agent or CoderAgent()
        self.reviewer_agent = reviewer_agent or ReviewerAgent()
        self.exec_tool = resolved_exec_tool
        self.tester_agent = tester_agent or TesterAgent(exec_tool=resolved_exec_tool)
        self.memory_store = memory_store or RedisMemory()
        self.dag_scheduler = dag_scheduler or DagScheduler(max_workers=4)

    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        working_task = dict(task)
        project_key = self.memory_store.project_key_for_task(working_task)
        history = self.memory_store.recent(project_key, limit=5)
        hints = _build_memory_hints(history)
        _apply_memory_hints(working_task, hints)
        _normalize_generation_target(working_task)
        target = str(working_task.get("target", "")).strip().lower()

        if target and target != "web":
            self.publish_event(
                working_task,
                client,
                "TASK_FAILED",
                {
                    "reason": "unsupported_target",
                    "target": target,
                    "supportedTargets": ["web"],
                },
            )
            self.memory_store.append(
                project_key,
                {
                    "intent": "code_change",
                    "status": "failed",
                    "reason": "unsupported_target",
                    "target": target,
                },
            )
            return

        if history:
            self.publish_event(
                working_task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "Memory",
                    "message": "Loaded project memory context.",
                    "projectKey": project_key,
                    "historyCount": len(history),
                    "lastTestCommand": hints.get("lastTestCommand"),
                    "lastDeployCommand": hints.get("lastDeployCommand"),
                },
            )

        prompt = str(working_task.get("prompt", "")).strip()
        decision = self.intent_agent.infer(prompt)
        if target == "web" and decision.intent != "code_change":
            decision = IntentDecision(
                backend=decision.backend,
                intent="code_change",
                confidence=max(decision.confidence, 0.75),
                reason="target=web forces code_change pipeline",
            )
        self.publish_event(
            working_task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "IntentAgent",
                "message": "Intent analysis completed.",
                "backend": decision.backend,
                "intent": decision.intent,
                "confidence": decision.confidence,
                "reason": decision.reason,
            },
        )

        plan = self.planner_agent.build_plan(prompt=prompt, intent=decision)
        self.publish_event(
            working_task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "PlannerAgent",
                "message": "Plan generated.",
                "planName": plan.plan_name,
                "steps": plan.steps,
            },
        )

        memory_record: dict[str, Any]
        try:
            if decision.intent == "code_change":
                memory_record = self._handle_code_change(working_task, client, plan)
                self.memory_store.append(project_key, memory_record)
                return

            if decision.intent in {"deploy", "test"}:
                memory_record = self._execute_with_sandbox(working_task, client, decision.intent, prompt, plan.plan_name)
                self.memory_store.append(project_key, memory_record)
                return

            self.publish_event(
                working_task,
                client,
                "TASK_DONE",
                {
                    "result": "planned",
                    "planName": plan.plan_name,
                    "steps": plan.steps,
                },
            )
            memory_record = {
                "intent": decision.intent,
                "planName": plan.plan_name,
                "status": "done",
                "result": "planned",
            }
            self.memory_store.append(project_key, memory_record)
        except Exception as exc:  # noqa: BLE001
            self.publish_event(
                working_task,
                client,
                "TASK_FAILED",
                {
                    "reason": "orchestrator_error",
                    "detail": str(exc),
                },
            )
            self.memory_store.append(
                project_key,
                {
                    "intent": decision.intent,
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": "orchestrator_error",
                    "detail": str(exc),
                },
            )

    def _publisher(self, task: dict[str, Any], client: ControlPlaneClient):
        def _emit(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
            self.publish_event(task, client, event_type, payload)

        return _emit

    def _handle_code_change(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
    ) -> dict[str, Any]:
        publisher = self._publisher(task, client)
        coded = self.coder_agent.execute(task, client, plan, publish_event=publisher)
        if not coded:
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "coder_failed",
            }

        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "Orchestrator",
                "message": "Running DAG stage in parallel.",
                "nodes": ["review", "test"],
                "maxWorkers": 2,
            },
        )
        try:
            dag_results = self.dag_scheduler.run(
                [
                    DagNode("review", lambda: self.reviewer_agent.review(task, client, plan, publish_event=publisher), ("coder",)),
                    DagNode("test", lambda: self.tester_agent.execute(task, client, plan, publish_event=publisher), ("coder",)),
                    DagNode("coder", lambda: True, ()),
                ]
            )
        except Exception as exc:  # noqa: BLE001
            self.publish_event(
                task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "Orchestrator",
                    "message": "Parallel pipeline failed.",
                    "error": str(exc),
                },
            )
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                {
                    "reason": "parallel_pipeline_error",
                    "planName": plan.plan_name,
                    "detail": str(exc),
                },
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "parallel_pipeline_error",
                "detail": str(exc),
            }

        review = dag_results["review"]
        test = dag_results["test"]
        if not isinstance(review, ReviewResult) or not isinstance(test, TesterResult):
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                {
                    "reason": "parallel_result_invalid",
                    "planName": plan.plan_name,
                },
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "parallel_result_invalid",
            }

        if not review.approved:
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                {
                    "reason": "review_rejected",
                    "planName": plan.plan_name,
                    "summary": review.summary,
                    "issues": review.issues,
                },
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "review_rejected",
                "summary": review.summary,
                "issues": review.issues,
                "testCommand": test.command,
            }

        if not test.success:
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                {
                    "reason": "test_failed",
                    "planName": plan.plan_name,
                    "summary": review.summary,
                    "testStatus": test.status,
                    "detail": test.reason,
                    "attempts": test.attempts,
                    "retries": test.retries,
                    "command": test.command,
                },
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "test_failed",
                "summary": review.summary,
                "testStatus": test.status,
                "detail": test.reason,
                "testCommand": test.command,
            }

        artifact: dict[str, Any] | None = None
        if _is_web_generation_task(task):
            try:
                artifact = self._publish_web_artifact(task, client)
            except Exception as exc:  # noqa: BLE001
                self.publish_event(
                    task,
                    client,
                    "TASK_FAILED",
                    {
                        "reason": "artifact_publish_failed",
                        "detail": str(exc),
                        "planName": plan.plan_name,
                    },
                )
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": "artifact_publish_failed",
                    "detail": str(exc),
                }

        self.publish_event(task, client, "TASK_DONE", _build_code_change_done_payload(plan.plan_name, review, test, artifact))
        return {
            "intent": "code_change",
            "planName": plan.plan_name,
            "status": "done",
            "result": "coded_reviewed_tested",
            "summary": review.summary,
            "testStatus": test.status,
            "testCommand": test.command,
            "traceId": test.trace_id,
            "runId": test.run_id,
            "artifactId": artifact.get("artifactId") if artifact else None,
        }

    def _publish_web_artifact(self, task: dict[str, Any], client: ControlPlaneClient) -> dict[str, Any]:
        workspace = _resolve_workspace(task)
        generated_files = _resolve_generated_files(task, workspace)
        bundle = build_export_zip(workspace, generated_files, file_name="export.zip")
        uploaded = self._try_upload_artifact(task, client, bundle)
        payload = _build_artifact_ready_payload(bundle, uploaded)
        self.publish_event(task, client, "ARTIFACT_READY", payload)
        return payload["artifact"]

    @staticmethod
    def _try_upload_artifact(task: dict[str, Any], client: ControlPlaneClient, bundle: ArtifactBundle) -> dict[str, Any] | None:
        upload = getattr(client, "upload_artifact", None)
        if not callable(upload):
            return None
        task_id = str(task.get("taskId", "")).strip()
        if not task_id:
            return None
        uploaded = upload(
            task_id,
            str(bundle.file_path),
            name=bundle.file_name,
            content_type=bundle.mime_type,
        )
        return uploaded if isinstance(uploaded, dict) else None

    def _execute_with_sandbox(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        intent: str,
        prompt: str,
        plan_name: str,
    ) -> dict[str, Any]:
        command = _resolve_command(task, intent, prompt)
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "ExecTool",
                "message": "Dispatching command to Java sandbox.",
                "intent": intent,
                "command": command,
            },
        )
        try:
            result = self.exec_tool.execute(task, command, prompt=prompt, intent=intent)
        except Exception as exc:  # noqa: BLE001
            self.publish_event(
                task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "ExecTool",
                    "message": "Sandbox execution request failed.",
                    "intent": intent,
                    "error": str(exc),
                },
            )
            self.publish_event(task, client, "TASK_FAILED", {"reason": "sandbox_request_failed", "detail": str(exc)})
            return {
                "intent": intent,
                "planName": plan_name,
                "status": "failed",
                "reason": "sandbox_request_failed",
                "detail": str(exc),
                "command": command,
            }

        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "ExecTool",
                "message": "Sandbox execution completed.",
                "intent": intent,
                "status": result.status,
                "exitCode": result.exit_code,
                "tool": result.tool,
                "traceId": result.trace_id,
                "runId": result.run_id,
            },
        )
        if result.ok:
            self.publish_event(
                task,
                client,
                "TASK_DONE",
                _build_done_payload(result, plan_name, intent),
            )
            payload = {
                "intent": intent,
                "planName": plan_name,
                "status": "done",
                "command": command,
                "result": "executed",
                "tool": result.tool,
                "toolVersion": result.tool_version,
                "traceId": result.trace_id,
                "runId": result.run_id,
            }
            if intent == "deploy":
                payload["deployCommand"] = command
            if intent == "test":
                payload["testCommand"] = command
            return payload
        self.publish_event(
            task,
            client,
            "TASK_FAILED",
            {
                "reason": _failure_reason(result),
                "status": result.status,
                "detail": result.reason,
                "retryable": result.retryable,
            },
        )
        payload = {
            "intent": intent,
            "planName": plan_name,
            "status": "failed",
            "reason": _failure_reason(result),
            "detail": result.reason,
            "command": command,
            "traceId": result.trace_id,
            "runId": result.run_id,
        }
        if intent == "deploy":
            payload["deployCommand"] = command
        if intent == "test":
            payload["testCommand"] = command
        return payload


def _resolve_command(task: dict[str, Any], intent: str, prompt: str) -> str:
    explicit = str(task.get("command", "")).strip()
    if explicit:
        return explicit
    env_key = "MVP_DEPLOY_COMMAND" if intent == "deploy" else "MVP_TEST_COMMAND"
    env_command = os.getenv(env_key, "").strip()
    if env_command:
        return env_command
    memory_key = "memoryLastDeployCommand" if intent == "deploy" else "memoryLastTestCommand"
    memory_command = str(task.get(memory_key, "")).strip()
    if memory_command:
        return memory_command
    if intent == "deploy":
        return "echo deploy_from_python_agent"
    if intent == "test":
        return "echo test_from_python_agent"
    return f"echo {prompt.strip() or 'sandbox_run'}"


def _build_done_payload(result: ExecResult, plan_name: str, intent: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "result": "executed",
        "intent": intent,
        "planName": plan_name,
        "status": result.status,
        "exitCode": result.exit_code,
        "retryable": result.retryable,
    }
    if result.tool:
        payload["tool"] = result.tool
    if result.tool_version:
        payload["toolVersion"] = result.tool_version
    if result.trace_id:
        payload["traceId"] = result.trace_id
    if result.run_id:
        payload["runId"] = result.run_id
    if result.output:
        payload["output"] = result.output
    return payload


def _build_code_change_done_payload(
    plan_name: str,
    review: ReviewResult,
    test: TesterResult,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "result": "coded_reviewed_tested",
        "planName": plan_name,
        "reviewApproved": review.approved,
        "reviewSummary": review.summary,
        "testStatus": test.status,
        "testAttempts": test.attempts,
        "testRetries": test.retries,
    }
    if artifact:
        payload["artifact"] = artifact
    if test.trace_id:
        payload["traceId"] = test.trace_id
    if test.run_id:
        payload["runId"] = test.run_id
    return payload


def _build_memory_hints(history: list[dict[str, Any]]) -> dict[str, str]:
    last_test_command = ""
    last_deploy_command = ""

    for item in reversed(history):
        if not last_test_command:
            candidate = _first_non_blank(item.get("testCommand"), item.get("command") if item.get("intent") == "test" else None)
            if candidate:
                last_test_command = candidate
        if not last_deploy_command:
            candidate = _first_non_blank(
                item.get("deployCommand"),
                item.get("command") if item.get("intent") == "deploy" else None,
            )
            if candidate:
                last_deploy_command = candidate
        if last_test_command and last_deploy_command:
            break

    hints: dict[str, str] = {}
    if last_test_command:
        hints["lastTestCommand"] = last_test_command
    if last_deploy_command:
        hints["lastDeployCommand"] = last_deploy_command
    return hints


def _apply_memory_hints(task: dict[str, Any], hints: dict[str, str]) -> None:
    test_command = hints.get("lastTestCommand", "").strip()
    deploy_command = hints.get("lastDeployCommand", "").strip()
    if test_command:
        task["memoryLastTestCommand"] = test_command
        if not str(task.get("testCommand", "")).strip():
            task["testCommand"] = test_command
    if deploy_command:
        task["memoryLastDeployCommand"] = deploy_command


def _first_non_blank(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _failure_reason(result: ExecResult) -> str:
    status = result.status.strip() if result.status else ""
    if status:
        return status
    if result.reason and result.reason.strip():
        return result.reason.strip()
    return "sandbox_exec_failed"


def _is_web_generation_task(task: dict[str, Any]) -> bool:
    target = str(task.get("target", "")).strip().lower()
    if target:
        return target == "web"
    assistant = str(task.get("assistant", "")).strip().lower()
    if assistant == "web":
        return True
    prompt = str(task.get("prompt", "")).strip().lower()
    web_markers = ("web", "website", "html", "page")
    return any(marker in prompt for marker in web_markers)


def _normalize_generation_target(task: dict[str, Any]) -> None:
    target = str(task.get("target", "")).strip().lower()
    if target:
        return
    assistant = str(task.get("assistant", "")).strip().lower()
    if assistant == "web":
        task["target"] = "web"


def _resolve_workspace(task: dict[str, Any]) -> Path:
    raw = str(task.get("workspacePath", "")).strip()
    if not raw:
        raw = "."
    return Path(raw).resolve(strict=False)


def _resolve_generated_files(task: dict[str, Any], workspace: Path) -> list[str]:
    files = task.get("_generated_files")
    if isinstance(files, list):
        normalized = [str(item).strip().replace("\\", "/") for item in files if str(item).strip()]
        if normalized:
            return normalized
    defaults = ["index.html", "styles.css", "app.js", "README.generated.md"]
    existing = [name for name in defaults if (workspace / name).exists()]
    if existing:
        return existing
    raise FileNotFoundError("no generated web files available for artifact packaging")


def _build_artifact_ready_payload(bundle: ArtifactBundle, uploaded: dict[str, Any] | None) -> dict[str, Any]:
    payload = bundle.to_event_payload()
    artifact = payload["artifact"]
    if not isinstance(artifact, dict):
        return payload

    if uploaded:
        artifact_id = str(uploaded.get("artifactId", "")).strip()
        if artifact_id:
            artifact["artifactId"] = artifact_id
        name = str(uploaded.get("name", "")).strip()
        if name:
            artifact["name"] = name
        content_type = str(uploaded.get("contentType", "")).strip()
        if content_type:
            artifact["mime"] = content_type
        sha = str(uploaded.get("sha256", "")).strip()
        if sha:
            artifact["hash"] = f"sha256:{sha}"
        size = uploaded.get("sizeBytes")
        if isinstance(size, int) and size >= 0:
            artifact["size"] = size
    return payload
