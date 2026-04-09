from __future__ import annotations

import os
import re
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


DEFAULT_FIX_LOOP_MAX_ATTEMPTS = 3


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
        target = str(working_task.get("target", "")).strip().lower()
        export_mode = _resolve_export_mode(working_task)
        working_task["_export_mode"] = export_mode

        if target and target != "web":
            self.publish_event(
                working_task,
                client,
                "TASK_FAILED",
                _task_failed_payload(
                    "unsupported_target",
                    target=target,
                    supportedTargets=["web"],
                ),
            )
            self.memory_store.append(
                project_key,
                {
                    "intent": "code_change",
                    "status": "failed",
                    "reason": "unsupported_target",
                    "errorCode": _error_code_from_reason("unsupported_target"),
                    "target": target,
                },
            )
            return

        if export_mode != "zip":
            self.publish_event(
                working_task,
                client,
                "TASK_FAILED",
                _task_failed_payload(
                    "unsupported_export_mode",
                    exportMode=export_mode,
                    supportedExportModes=["zip"],
                ),
            )
            self.memory_store.append(
                project_key,
                {
                    "intent": "code_change",
                    "status": "failed",
                    "reason": "unsupported_export_mode",
                    "errorCode": _error_code_from_reason("unsupported_export_mode"),
                    "exportMode": export_mode,
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

            if decision.intent == "llm_key_missing":
                self.publish_event(
                    working_task,
                    client,
                    "TASK_FAILED",
                    _task_failed_payload(
                        "llm_key_missing",
                        planName=plan.plan_name,
                        detail=decision.reason,
                    ),
                )
                self.memory_store.append(
                    project_key,
                    {
                        "intent": decision.intent,
                        "planName": plan.plan_name,
                        "status": "failed",
                        "reason": "llm_key_missing",
                        "errorCode": _error_code_from_reason("llm_key_missing"),
                        "detail": decision.reason,
                    },
                )
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
                _task_failed_payload("orchestrator_error", detail=str(exc)),
            )
            self.memory_store.append(
                project_key,
                {
                    "intent": decision.intent,
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": "orchestrator_error",
                    "errorCode": _error_code_from_reason("orchestrator_error"),
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
                _task_failed_payload(
                    "parallel_pipeline_error",
                    planName=plan.plan_name,
                    detail=str(exc),
                ),
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "parallel_pipeline_error",
                "errorCode": _error_code_from_reason("parallel_pipeline_error"),
                "detail": str(exc),
            }

        review = dag_results["review"]
        test = dag_results["test"]
        if not isinstance(review, ReviewResult) or not isinstance(test, TesterResult):
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                _task_failed_payload("parallel_result_invalid", planName=plan.plan_name),
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "parallel_result_invalid",
                "errorCode": _error_code_from_reason("parallel_result_invalid"),
            }

        if not review.approved:
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                _task_failed_payload(
                    "review_rejected",
                    planName=plan.plan_name,
                    summary=review.summary,
                    issues=review.issues,
                    riskLevel=review.risk_level,
                ),
            )
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "review_rejected",
                "errorCode": _error_code_from_reason("review_rejected"),
                "summary": review.summary,
                "issues": review.issues,
                "riskLevel": review.risk_level,
                "testCommand": test.command,
            }

        if not test.success:
            return self._run_fix_loop(
                task=task,
                client=client,
                plan=plan,
                review=review,
                initial_test=test,
                publish_event=publisher,
            )

        artifact: dict[str, Any] | None = None
        if _is_web_generation_task(task):
            try:
                artifact = self._publish_web_artifact(task, client)
            except Exception as exc:  # noqa: BLE001
                self.publish_event(
                    task,
                    client,
                    "TASK_FAILED",
                    _task_failed_payload(
                        "artifact_publish_failed",
                        planName=plan.plan_name,
                        detail=str(exc),
                    ),
                )
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": "artifact_publish_failed",
                    "errorCode": _error_code_from_reason("artifact_publish_failed"),
                    "detail": str(exc),
                }

        self.publish_event(
            task,
            client,
            "TASK_DONE",
            _build_code_change_done_payload(plan.plan_name, review, test, artifact=artifact),
        )
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
        bundle = build_export_zip(workspace, generated_files, file_name=_artifact_file_name(task))
        uploaded = self._try_upload_artifact(task, client, bundle)
        payload = _build_artifact_ready_payload(bundle, uploaded)
        payload["target"] = "web"
        payload["exportMode"] = _resolve_export_mode(task)
        template_id = _resolve_template_id(task)
        if template_id:
            payload["templateId"] = template_id
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

    def _run_fix_loop(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        review: ReviewResult,
        initial_test: TesterResult,
        publish_event,
    ) -> dict[str, Any]:
        max_attempts = _resolve_fix_loop_max_attempts()
        original_prompt = str(task.get("prompt", "")).strip()
        current_test = initial_test
        last_test_error = _build_test_error_text(current_test)

        for attempt in range(1, max_attempts + 1):
            latest_diff = _resolve_latest_diff(task)
            fix_prompt = _build_fix_loop_prompt(
                original_prompt=original_prompt,
                latest_diff=latest_diff,
                last_test_error=last_test_error,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            task["prompt"] = fix_prompt

            self.publish_event(
                task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "Orchestrator",
                    "message": "Fix loop attempt started.",
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "lastTestError": last_test_error,
                },
            )

            coded = self.coder_agent.execute(task, client, plan, publish_event=publish_event)
            if not coded:
                self.publish_event(
                    task,
                    client,
                    "ASSISTANT_OUTPUT",
                    {
                        "stage": "Orchestrator",
                        "message": "Fix loop produced no substantial patch.",
                        "attempt": attempt,
                        "maxAttempts": max_attempts,
                    },
                )

            current_test = self.tester_agent.execute(task, client, plan, publish_event=publish_event)
            if current_test.success:
                task["prompt"] = original_prompt
                self.publish_event(
                    task,
                    client,
                    "TASK_DONE",
                    _build_code_change_done_payload(
                        plan_name=plan.plan_name,
                        review=review,
                        test=current_test,
                        fix_attempt=attempt,
                        max_attempts=max_attempts,
                    ),
                )
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "done",
                    "result": "coded_reviewed_tested",
                    "summary": review.summary,
                    "testStatus": current_test.status,
                    "testCommand": current_test.command,
                    "traceId": current_test.trace_id,
                    "runId": current_test.run_id,
                    "fixLoopAttempt": attempt,
                    "fixLoopMaxAttempts": max_attempts,
                }

            last_test_error = _build_test_error_text(current_test)
            self.publish_event(
                task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "Orchestrator",
                    "message": "Fix loop validation failed.",
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "lastTestError": last_test_error,
                },
            )

        task["prompt"] = original_prompt
        self.publish_event(
            task,
            client,
            "TASK_FAILED",
            _task_failed_payload(
                "fix_loop_exhausted",
                planName=plan.plan_name,
                summary=review.summary,
                issues=review.issues,
                riskLevel=review.risk_level,
                attempt=max_attempts,
                maxAttempts=max_attempts,
                lastTestError=last_test_error,
            ),
        )
        return {
            "intent": "code_change",
            "planName": plan.plan_name,
            "status": "failed",
            "reason": "fix_loop_exhausted",
            "errorCode": _error_code_from_reason("fix_loop_exhausted"),
            "summary": review.summary,
            "issues": review.issues,
            "riskLevel": review.risk_level,
            "testStatus": current_test.status,
            "detail": current_test.reason,
            "testCommand": current_test.command,
            "fixLoopAttempt": max_attempts,
            "fixLoopMaxAttempts": max_attempts,
            "lastTestError": last_test_error,
        }

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
            self.publish_event(
                task,
                client,
                "TASK_FAILED",
                _task_failed_payload("sandbox_request_failed", detail=str(exc)),
            )
            return {
                "intent": intent,
                "planName": plan_name,
                "status": "failed",
                "reason": "sandbox_request_failed",
                "errorCode": _error_code_from_reason("sandbox_request_failed"),
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
        failure_reason = _failure_reason(result)
        self.publish_event(
            task,
            client,
            "TASK_FAILED",
            _task_failed_payload(
                failure_reason,
                status=result.status,
                detail=result.reason,
                retryable=result.retryable,
            ),
        )
        payload = {
            "intent": intent,
            "planName": plan_name,
            "status": "failed",
            "reason": failure_reason,
            "errorCode": _error_code_from_reason(failure_reason),
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
    fix_attempt: int | None = None,
    max_attempts: int | None = None,
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
    if fix_attempt is not None:
        payload["attempt"] = fix_attempt
    if max_attempts is not None:
        payload["maxAttempts"] = max_attempts
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


def _resolve_fix_loop_max_attempts() -> int:
    raw = os.getenv("MVP_FIX_LOOP_MAX_ATTEMPTS", str(DEFAULT_FIX_LOOP_MAX_ATTEMPTS)).strip()
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_FIX_LOOP_MAX_ATTEMPTS
    return max(1, min(parsed, DEFAULT_FIX_LOOP_MAX_ATTEMPTS))


def _resolve_latest_diff(task: dict[str, Any]) -> str:
    direct = task.get("latestDiff")
    if isinstance(direct, str) and direct.strip():
        return direct

    generated = task.get("generatedDiffs")
    if isinstance(generated, list):
        for item in reversed(generated):
            text = str(item).strip()
            if text:
                return text

    for key in ("diff", "patch"):
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _build_test_error_text(test_result: TesterResult) -> str:
    return _first_non_blank(test_result.reason, test_result.status, "test_failed") or "test_failed"


def _build_fix_loop_prompt(
    *,
    original_prompt: str,
    latest_diff: str,
    last_test_error: str,
    attempt: int,
    max_attempts: int,
) -> str:
    return (
        "Fix_Loop repair task.\n"
        f"Attempt: {attempt}/{max_attempts}\n\n"
        "Original task:\n"
        f"{original_prompt or '(empty)'}\n\n"
        "Current unified diff:\n"
        f"{latest_diff or '(no diff)'}\n\n"
        "Latest test error:\n"
        f"{last_test_error or '(unknown)'}\n\n"
        "Apply a minimal, safe fix and return full updated file content."
    )


def _task_failed_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload = {"reason": reason, "errorCode": _error_code_from_reason(reason)}
    payload.update(extra)
    return payload


def _error_code_from_reason(reason: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(reason).strip()).strip("_")
    if not normalized:
        return "UNKNOWN_ERROR"
    return normalized.upper()


def _is_web_generation_task(task: dict[str, Any]) -> bool:
    target = str(task.get("target", "")).strip().lower()
    if target:
        return target == "web"
    prompt = str(task.get("prompt", "")).strip().lower()
    return any(marker in prompt for marker in ("web", "website", "html", "page"))


def _resolve_export_mode(task: dict[str, Any]) -> str:
    explicit = str(task.get("exportMode", "")).strip().lower()
    if explicit:
        return explicit
    alternate = str(task.get("export_mode", "")).strip().lower()
    if alternate:
        return alternate
    return "zip"


def _artifact_file_name(task: dict[str, Any]) -> str:
    export_mode = _resolve_export_mode(task)
    if export_mode == "zip":
        return "export.zip"
    return f"export.{export_mode}"


def _resolve_template_id(task: dict[str, Any]) -> str | None:
    explicit = str(task.get("templateId", "")).strip()
    if explicit:
        return explicit
    alternate = str(task.get("template_id", "")).strip()
    if alternate:
        return alternate
    template_runtime = str(task.get("_template_id", "")).strip()
    return template_runtime or None


def _resolve_workspace(task: dict[str, Any]) -> Path:
    raw = str(task.get("workspacePath", "")).strip()
    if not raw:
        raw = "."
    return Path(raw).resolve(strict=False)


def _resolve_generated_files(task: dict[str, Any], workspace: Path) -> list[str]:
    generated = task.get("_generated_files")
    if isinstance(generated, list):
        files = [str(item).strip().replace("\\", "/") for item in generated if str(item).strip()]
        if files:
            return files
    defaults = ["index.html", "styles.css", "app.js", "README.generated.md"]
    existing = [name for name in defaults if (workspace / name).exists()]
    if existing:
        return existing
    raise FileNotFoundError("no generated web files available for artifact packaging")


def _build_artifact_ready_payload(bundle: ArtifactBundle, uploaded: dict[str, Any] | None) -> dict[str, Any]:
    payload = bundle.to_event_payload()
    artifact = payload.get("artifact")
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
