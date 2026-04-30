from __future__ import annotations

import os
from pathlib import Path
from time import monotonic
from typing import Any

from agents.base_agent import BaseAgent
from agents.coder_agent import CoderAgent
from agents.intent_agent import IntentAgent
from agents.planner_agent import PlanResult, PlannerAgent
from agents.reviewer_agent import ReviewResult, ReviewerAgent
from agents.tester_agent import TesterAgent, TesterResult
from client.control_plane_client import ControlPlaneClient
from generators.validation_gate import ValidationGate
from memory.redis_memory import RedisMemory
from orchestrator.dag_scheduler import DagNode, DagScheduler
from orchestrator.distributed_lock import DistributedTaskLock
from orchestrator.langgraph_runtime import LangGraphExecutionResult, LangGraphRuntime
from plugins.contracts import PluginContext
from plugins.registry import PluginRegistry
from tools.exec_tool import ExecResult, ExecTool
from utils.artifact_utils import ArtifactBundle, build_export_zip
from utils.circuit_breaker import CircuitBreakerOpenError
from utils.observability import (
    TaskObservability,
    attach_terminal_observability,
    ensure_task_observability,
    observe_task_span,
)


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
        validation_gate: ValidationGate | None = None,
        distributed_lock: DistributedTaskLock | None = None,
        langgraph_runtime: LangGraphRuntime | None = None,
        plugin_registry: PluginRegistry | None = None,
        engine: str | None = None,
    ) -> None:
        super().__init__()
        resolved_exec_tool = exec_tool or ExecTool()
        resolved_plugin_registry = plugin_registry or PluginRegistry()
        self.intent_agent = intent_agent or IntentAgent()
        self.planner_agent = planner_agent or PlannerAgent()
        self.coder_agent = coder_agent or CoderAgent(plugin_registry=resolved_plugin_registry)
        self.reviewer_agent = reviewer_agent or ReviewerAgent()
        self.exec_tool = resolved_exec_tool
        self.tester_agent = tester_agent or TesterAgent(exec_tool=resolved_exec_tool, plugin_registry=resolved_plugin_registry)
        self.memory_store = memory_store or RedisMemory()
        self.dag_scheduler = dag_scheduler or DagScheduler(max_workers=4)
        self.validation_gate = validation_gate or ValidationGate()
        self.distributed_lock = distributed_lock or DistributedTaskLock()
        self.langgraph_runtime = langgraph_runtime or LangGraphRuntime()
        self.plugin_registry = resolved_plugin_registry
        self.engine = _resolve_agent_engine(engine)

    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        working_task = dict(task)
        working_task["_agentEngine"] = self.engine
        working_task["_executionPath"] = "legacy"
        _normalize_generation_target(working_task)

        task_id = str(working_task.get("taskId", "")).strip()
        if not task_id:
            raise ValueError("task.taskId is required")
        ensure_task_observability(working_task, engine=self.engine)

        validation_error = _validate_generation_request(working_task)
        if validation_error is not None:
            self.publish_event(
                working_task,
                client,
                "TASK_FAILED",
                self._terminal_payload(
                    working_task,
                    validation_error,
                    task_status="failed",
                    intent="validation",
                    reason=str(validation_error.get("reason", "")).strip(),
                ),
            )
            return

        lease = self.distributed_lock.acquire(task_id)
        if not lease.acquired:
            return

        try:
            self._handle_task_locked(working_task, client)
        finally:
            lease.release()

    def _handle_task_locked(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        with observe_task_span(task, "memory_context", stage="Memory"):
            project_key = self.memory_store.project_key_for_task(task)
            history = self.memory_store.recent(project_key, limit=5)
            hints = _build_memory_hints(history)
            _apply_memory_hints(task, hints)

        if history:
            self.publish_event(
                task,
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

        prompt = str(task.get("prompt", "")).strip()
        observation = ensure_task_observability(task, engine=self.engine)
        with observe_task_span(task, "intent_inference", stage="IntentAgent"):
            decision = self._infer_intent(task, prompt, observation)
        task["intent"] = decision.intent
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "IntentAgent",
                "message": "Intent analysis completed.",
                "backend": decision.backend,
                "engine": self.engine,
                "intent": decision.intent,
                "confidence": decision.confidence,
                "reason": decision.reason,
            },
        )

        with observe_task_span(task, "plan_build", stage="PlannerAgent", attributes={"intent": decision.intent}):
            plan = self.planner_agent.build_plan_with_observability(
                prompt=prompt,
                intent=decision,
                observation=observation,
            )
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "PlannerAgent",
                "message": "Plan generated.",
                "engine": self.engine,
                "planName": plan.plan_name,
                "steps": plan.steps,
            },
        )

        memory_record: dict[str, Any]
        try:
            if decision.intent == "llm_key_missing":
                base_payload = _failure_payload(
                    "llm_key_missing",
                    plan_name=plan.plan_name,
                    detail=decision.reason,
                )
                payload = self._terminal_payload(
                    task,
                    base_payload,
                    task_status="failed",
                    intent=decision.intent,
                    reason=str(base_payload.get("reason", "")).strip(),
                )
                self.publish_event(task, client, "TASK_FAILED", payload)
                memory_record = {
                    "intent": decision.intent,
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": payload["reason"],
                    "errorCode": payload["errorCode"],
                    "detail": payload["detail"],
                }
                self.memory_store.append(project_key, memory_record)
                return

            langgraph_result = self._maybe_execute_langgraph(task, client, decision.intent, plan)
            if langgraph_result is not None:
                terminal_payload = self._terminal_payload(
                    task,
                    langgraph_result.terminal_payload,
                    task_status=langgraph_result.task_status,
                    intent=decision.intent,
                    reason=langgraph_result.reason,
                )
                self.publish_event(task, client, langgraph_result.terminal_event_type, terminal_payload)
                self.memory_store.append(project_key, langgraph_result.memory_record)
                return

            if decision.intent == "code_change":
                memory_record = self._handle_code_change(task, client, plan)
                self.memory_store.append(project_key, memory_record)
                return

            if decision.intent in {"deploy", "test"}:
                memory_record = self._execute_with_sandbox(task, client, decision.intent, prompt, plan.plan_name)
                self.memory_store.append(project_key, memory_record)
                return

            payload = {
                "result": "planned",
                "intent": decision.intent,
                "planName": plan.plan_name,
                "steps": plan.steps,
                "executionPath": "legacy",
            }
            self.publish_event(
                task,
                client,
                "TASK_DONE",
                self._terminal_payload(task, payload, task_status="done", intent=decision.intent),
            )
            memory_record = {
                "intent": decision.intent,
                "planName": plan.plan_name,
                "status": "done",
                "result": "planned",
                "executionPath": "legacy",
            }
            self.memory_store.append(project_key, memory_record)
        except Exception as exc:  # noqa: BLE001
            base_payload = _failure_payload("orchestrator_error", detail=str(exc))
            payload = self._terminal_payload(
                task,
                base_payload,
                task_status="failed",
                intent=decision.intent,
                reason=str(base_payload.get("reason", "")).strip(),
            )
            self.publish_event(task, client, "TASK_FAILED", payload)
            self.memory_store.append(
                project_key,
                {
                    "intent": decision.intent,
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": payload["reason"],
                    "errorCode": payload["errorCode"],
                    "detail": payload["detail"],
                },
            )

    def _infer_intent(
        self,
        task: dict[str, Any],
        prompt: str,
        observation: TaskObservability,
    ):
        backend = self.intent_agent.llm_client.settings.backend
        cache_cursor = self.intent_agent.llm_client.cache_event_cursor()
        decision = self.intent_agent.infer(prompt)
        self.intent_agent.llm_client.record_cache_metrics(
            observation,
            stage="IntentAgent",
            backend=backend,
            since_sequence=cache_cursor,
        )
        return decision

    def _publisher(self, task: dict[str, Any], client: ControlPlaneClient):
        def _emit(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
            self.publish_event(task, client, event_type, payload)

        return _emit

    def _terminal_payload(
        self,
        task: dict[str, Any],
        payload: dict[str, Any],
        *,
        task_status: str,
        intent: str = "",
        reason: str = "",
        fix_loop_attempts: int = 0,
        fix_loop_success: bool | None = None,
    ) -> dict[str, Any]:
        output = dict(payload)
        output.setdefault("executionPath", str(task.get("_executionPath", "")).strip() or "legacy")
        return attach_terminal_observability(
            task,
            output,
            task_status=task_status,
            intent=intent,
            reason=reason,
            generation_target=_generation_target_for_metrics(task),
            fix_loop_attempts=fix_loop_attempts,
            fix_loop_success=fix_loop_success,
        )

    def _maybe_execute_langgraph(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        intent: str,
        plan: PlanResult,
    ) -> LangGraphExecutionResult | None:
        if self.engine != "langgraph":
            return None
        if not self.langgraph_runtime.supports(intent):
            task["_executionPath"] = "legacy"
            self.publish_event(
                task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "LangGraphRuntime",
                    "message": "Intent not migrated yet, falling back to legacy pipeline.",
                    "intent": intent,
                    "fallbackEngine": "legacy",
                },
            )
            return None

        publisher = self._publisher(task, client)
        with observe_task_span(task, "langgraph_runtime", stage="LangGraphRuntime", attributes={"intent": intent}):
            result = self.langgraph_runtime.execute(
                intent=intent,
                publish_event=publisher,
                analyze_handler=lambda: self._build_langgraph_analyze_result(plan),
                test_handler=lambda: self._execute_langgraph_test(task, client, plan, publisher),
            )
        if result.handled:
            task["_executionPath"] = "langgraph"
            return result
        task["_executionPath"] = "legacy"
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "LangGraphRuntime",
                "message": "LangGraph runtime skipped current intent, falling back to legacy pipeline.",
                "intent": intent,
                "fallbackEngine": "legacy",
            },
        )
        return None

    @staticmethod
    def _build_langgraph_analyze_result(plan: PlanResult) -> LangGraphExecutionResult:
        payload = {
            "result": "planned",
            "intent": "analyze",
            "planName": plan.plan_name,
            "steps": plan.steps,
            "executionPath": "langgraph",
        }
        memory_record = {
            "intent": "analyze",
            "planName": plan.plan_name,
            "status": "done",
            "result": "planned",
            "executionPath": "langgraph",
        }
        return LangGraphExecutionResult(
            handled=True,
            terminal_event_type="TASK_DONE",
            terminal_payload=payload,
            memory_record=memory_record,
            task_status="done",
            reason="planned",
        )

    def _execute_langgraph_test(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publisher,
    ) -> LangGraphExecutionResult:
        with observe_task_span(task, "test_execution", stage="TesterAgent", attributes={"runtime": "langgraph"}):
            result = self.tester_agent.execute(task, client, plan, publish_event=publisher)
        if result.success:
            payload: dict[str, Any] = {
                "result": "executed",
                "intent": "test",
                "planName": plan.plan_name,
                "status": result.status,
                "command": result.command,
                "attempts": result.attempts,
                "retries": result.retries,
                "executionPath": "langgraph",
            }
            if result.trace_id:
                payload["traceId"] = result.trace_id
            if result.run_id:
                payload["runId"] = result.run_id
            memory_record = {
                "intent": "test",
                "planName": plan.plan_name,
                "status": "done",
                "command": result.command,
                "result": "executed",
                "traceId": result.trace_id,
                "runId": result.run_id,
                "executionPath": "langgraph",
            }
            return LangGraphExecutionResult(
                handled=True,
                terminal_event_type="TASK_DONE",
                terminal_payload=payload,
                memory_record=memory_record,
                task_status="done",
                reason="executed",
            )

        payload = _failure_payload(
            result.status or result.reason or "test_failed",
            status=result.status,
            detail=result.reason,
            command=result.command,
        )
        payload["executionPath"] = "langgraph"
        memory_record = {
            "intent": "test",
            "planName": plan.plan_name,
            "status": "failed",
            "reason": payload["reason"],
            "errorCode": payload["errorCode"],
            "detail": payload.get("detail"),
            "command": result.command,
            "traceId": result.trace_id,
            "runId": result.run_id,
            "executionPath": "langgraph",
        }
        return LangGraphExecutionResult(
            handled=True,
            terminal_event_type="TASK_FAILED",
            terminal_payload=payload,
            memory_record=memory_record,
            task_status="failed",
            reason=str(payload.get("reason", "")).strip(),
        )

    def _handle_code_change(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
    ) -> dict[str, Any]:
        max_fix_attempts = _resolve_fix_loop_max_attempts()
        fix_attempt = 0
        last_test_error = ""

        while True:
            task["fixLoopAttempt"] = fix_attempt
            if last_test_error:
                task["lastTestError"] = last_test_error
            else:
                task.pop("lastTestError", None)

            if fix_attempt > 0:
                self.publish_event(
                    task,
                    client,
                    "ASSISTANT_OUTPUT",
                    {
                        "stage": "Orchestrator",
                        "message": "Fix loop attempt started.",
                        "attempt": fix_attempt,
                        "maxAttempts": max_fix_attempts,
                        "lastTestError": last_test_error,
                    },
                )

            publisher = self._publisher(task, client)
            with observe_task_span(task, "code_generation", stage="CoderAgent", attributes={"attempt": fix_attempt}):
                coded = self.coder_agent.execute(task, client, plan, publish_event=publisher)
            if not coded:
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": "coder_failed",
                    "errorCode": _error_code_from_reason("coder_failed"),
                }

            with observe_task_span(task, "validation_gate", stage="ValidationGate"):
                validation = self.validation_gate.validate(task, _resolve_workspace(task))
            if not validation.ok:
                last_test_error = validation.summary
                if fix_attempt < max_fix_attempts:
                    fix_attempt += 1
                    continue
                base_payload = _failure_payload(
                    "fix_loop_exhausted",
                    plan_name=plan.plan_name,
                    attempt=fix_attempt,
                    maxAttempts=max_fix_attempts,
                    lastTestError=last_test_error,
                )
                payload = self._terminal_payload(
                    task,
                    base_payload,
                    task_status="failed",
                    intent="code_change",
                    reason=str(base_payload.get("reason", "")).strip(),
                    fix_loop_attempts=fix_attempt,
                    fix_loop_success=False,
                )
                self.publish_event(task, client, "TASK_FAILED", payload)
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": payload["reason"],
                    "errorCode": payload["errorCode"],
                    "detail": last_test_error,
                }

            with observe_task_span(task, "review_and_test", stage="Orchestrator"):
                dag_results = self._run_review_and_test(task, client, plan, publisher)
            if dag_results is None:
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": "parallel_pipeline_error",
                    "errorCode": _error_code_from_reason("parallel_pipeline_error"),
                }

            review = dag_results["review"]
            test = dag_results["test"]
            if not isinstance(review, ReviewResult) or not isinstance(test, TesterResult):
                base_payload = _failure_payload("parallel_result_invalid", plan_name=plan.plan_name)
                payload = self._terminal_payload(
                    task,
                    base_payload,
                    task_status="failed",
                    intent="code_change",
                    reason=str(base_payload.get("reason", "")).strip(),
                    fix_loop_attempts=fix_attempt,
                    fix_loop_success=False,
                )
                self.publish_event(task, client, "TASK_FAILED", payload)
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": payload["reason"],
                    "errorCode": payload["errorCode"],
                }

            if not review.approved:
                base_payload = _failure_payload(
                    "review_rejected",
                    plan_name=plan.plan_name,
                    summary=review.summary,
                    issues=review.issues,
                    riskLevel=review.risk_level,
                )
                payload = self._terminal_payload(
                    task,
                    base_payload,
                    task_status="failed",
                    intent="code_change",
                    reason=str(base_payload.get("reason", "")).strip(),
                    fix_loop_attempts=fix_attempt,
                    fix_loop_success=False,
                )
                self.publish_event(task, client, "TASK_FAILED", payload)
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": payload["reason"],
                    "errorCode": payload["errorCode"],
                    "summary": review.summary,
                    "issues": review.issues,
                    "riskLevel": review.risk_level,
                    "testCommand": test.command,
                }

            if not test.success:
                last_test_error = str(test.reason or test.status or "test_failed").strip()
                if fix_attempt < max_fix_attempts:
                    fix_attempt += 1
                    continue
                base_payload = _failure_payload(
                    "fix_loop_exhausted",
                    plan_name=plan.plan_name,
                    attempt=fix_attempt,
                    maxAttempts=max_fix_attempts,
                    lastTestError=last_test_error,
                    testStatus=test.status,
                    command=test.command,
                )
                payload = self._terminal_payload(
                    task,
                    base_payload,
                    task_status="failed",
                    intent="code_change",
                    reason=str(base_payload.get("reason", "")).strip(),
                    fix_loop_attempts=fix_attempt,
                    fix_loop_success=False,
                )
                self.publish_event(task, client, "TASK_FAILED", payload)
                return {
                    "intent": "code_change",
                    "planName": plan.plan_name,
                    "status": "failed",
                    "reason": payload["reason"],
                    "errorCode": payload["errorCode"],
                    "detail": last_test_error,
                    "testCommand": test.command,
                }

            artifact: dict[str, Any] | None = None
            if _should_publish_generated_artifact(task):
                artifact = self._publish_generated_artifact(task, client, test)

            base_done_payload = _build_code_change_done_payload(
                plan.plan_name,
                review,
                test,
                artifact=artifact,
                attempt=fix_attempt if fix_attempt > 0 else None,
                max_attempts=max_fix_attempts if fix_attempt > 0 else None,
                target=_resolved_generation_target(task),
            )
            done_payload = self._terminal_payload(
                task,
                base_done_payload,
                task_status="done",
                intent="code_change",
                fix_loop_attempts=fix_attempt,
                fix_loop_success=True if fix_attempt > 0 else None,
            )
            self.publish_event(task, client, "TASK_DONE", done_payload)
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

    def _run_review_and_test(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publisher,
    ) -> dict[str, Any] | None:
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
            return self.dag_scheduler.run(
                [
                    DagNode("review", lambda: self._run_reviewer_with_plugins(task, client, plan, publisher), ("coder",)),
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
            payload = _failure_payload("parallel_pipeline_error", plan_name=plan.plan_name, detail=str(exc))
            self.publish_event(task, client, "TASK_FAILED", payload)
            return None

    def _run_reviewer_with_plugins(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publisher,
    ) -> ReviewResult:
        plugin_context = PluginContext(task=task, client=client, plan=plan, publish_event=publisher)
        plugins = self.plugin_registry.resolve_reviewer_plugins(plugin_context)
        if not plugins:
            return self.reviewer_agent.review(task, client, plan, publish_event=publisher)

        for plugin in plugins:
            manifest = plugin.manifest
            task["_activeReviewerPlugin"] = manifest.plugin_id
            breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
            publisher(
                {
                    "stage": "ReviewerPlugin",
                    "message": "Executing reviewer plugin.",
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
                with observe_task_span(
                    task,
                    "reviewer_plugin",
                    stage="ReviewerPlugin",
                    attributes={"pluginId": manifest.plugin_id},
                ):
                    result = self.plugin_registry.execute_plugin(
                        manifest.plugin_id,
                        lambda: plugin.review(plugin_context),
                    )
                publisher(ReviewerAgent.publish_payload(plan, result))
                return result
            except CircuitBreakerOpenError:
                breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
                publisher(
                    {
                        "stage": "ReviewerPlugin",
                        "message": "Plugin skipped due to circuit breaker, falling back to built-in implementation.",
                        "pluginId": manifest.plugin_id,
                        "breakerStatus": breaker_state.get("status"),
                        "failureCount": breaker_state.get("failureCount"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
                publisher(
                    {
                        "stage": "ReviewerPlugin",
                        "message": "Reviewer plugin failed, falling back to built-in reviewer.",
                        "pluginId": manifest.plugin_id,
                        "breakerStatus": breaker_state.get("status"),
                        "failureCount": breaker_state.get("failureCount"),
                        "error": str(exc),
                    }
                )
        task.pop("_activeReviewerPlugin", None)
        return self.reviewer_agent.review(task, client, plan, publish_event=publisher)

    def _publish_generated_artifact(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        test: TesterResult,
    ) -> dict[str, Any]:
        target = _resolved_generation_target(task)
        template_id = str(task.get("templateId", "")).strip() or "default"
        export_mode = str(task.get("exportMode", "")).strip().lower() or "zip"
        task_id = str(task.get("taskId", "")).strip()
        build_id = f"build_{task_id}_{target}"

        self.publish_event(
            task,
            client,
            "SPEC_PROPOSED",
            {
                "target": target,
                "templateId": template_id,
                "exportMode": export_mode,
                "path": "spec.json",
                "schemaVersion": "v1",
                "traceId": test.trace_id,
                "runId": test.run_id,
                "artifact": {
                    "artifactId": f"art_spec_{task_id}",
                    "type": "spec",
                    "name": "spec.json",
                },
            },
        )

        workspace = _resolve_workspace(task)
        generated_files = _resolve_generated_files(task, workspace)
        self.publish_event(
            task,
            client,
            "BUILD_STARTED",
            {
                "buildId": build_id,
                "tool": "artifact.export.zip",
                "target": target,
                "traceId": test.trace_id,
                "runId": test.run_id,
            },
        )
        self.publish_event(
            task,
            client,
            "BUILD_LOG",
            {
                "buildId": build_id,
                "level": "info",
                "message": "Packaging generated web files into export.zip artifact.",
                "traceId": test.trace_id,
                "runId": test.run_id,
            },
        )

        started_at = monotonic()
        with observe_task_span(task, "artifact_publish", stage="Artifact"):
            bundle = build_export_zip(workspace, generated_files, file_name="export.zip")
            uploaded = self._try_upload_artifact(task, client, bundle)
        payload = _build_artifact_ready_payload(task, bundle, uploaded, target, template_id, export_mode)
        self.publish_event(
            task,
            client,
            "BUILD_DONE",
            {
                "buildId": build_id,
                "status": "success",
                "durationMs": max(0, int((monotonic() - started_at) * 1000)),
                "traceId": test.trace_id,
                "runId": test.run_id,
            },
        )
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
            with observe_task_span(task, "sandbox_execute", stage="ExecTool", attributes={"intent": intent}):
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
            base_payload = _failure_payload("sandbox_request_failed", detail=str(exc))
            payload = self._terminal_payload(
                task,
                base_payload,
                task_status="failed",
                intent=intent,
                reason=str(base_payload.get("reason", "")).strip(),
            )
            self.publish_event(task, client, "TASK_FAILED", payload)
            return {
                "intent": intent,
                "planName": plan_name,
                "status": "failed",
                "reason": payload["reason"],
                "errorCode": payload["errorCode"],
                "detail": payload["detail"],
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
                self._terminal_payload(
                    task,
                    _build_done_payload(result, plan_name, intent),
                    task_status="done",
                    intent=intent,
                ),
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

        payload = _failure_payload(
            _failure_reason(result),
            status=result.status,
            detail=result.reason,
            retryable=result.retryable,
        )
        self.publish_event(
            task,
            client,
            "TASK_FAILED",
            self._terminal_payload(
                task,
                payload,
                task_status="failed",
                intent=intent,
                reason=str(payload.get("reason", "")).strip(),
            ),
        )
        output = {
            "intent": intent,
            "planName": plan_name,
            "status": "failed",
            "reason": payload["reason"],
            "errorCode": payload["errorCode"],
            "detail": payload.get("detail"),
            "command": command,
            "traceId": result.trace_id,
            "runId": result.run_id,
        }
        if intent == "deploy":
            output["deployCommand"] = command
        if intent == "test":
            output["testCommand"] = command
        return output


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
    *,
    artifact: dict[str, Any] | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
    target: str = "",
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
    if target:
        payload["intent"] = "code_change"
    if artifact:
        payload["artifact"] = artifact
    if attempt is not None:
        payload["attempt"] = attempt
    if max_attempts is not None:
        payload["maxAttempts"] = max_attempts
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


def _validate_generation_request(task: dict[str, Any]) -> dict[str, Any] | None:
    target = str(task.get("target", "")).strip().lower()
    export_mode = str(task.get("exportMode", "")).strip().lower()
    if target and target not in {"web", "backend", "fullstack"}:
        return _failure_payload("unsupported_target")
    if export_mode and export_mode != "zip":
        return _failure_payload("unsupported_export_mode")
    return None


def _resolve_fix_loop_max_attempts() -> int:
    raw = os.getenv("MVP_FIX_LOOP_MAX_ATTEMPTS", "").strip()
    if not raw:
        return 3
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(value, 3))


def _error_code_from_reason(reason: str) -> str:
    text = (reason or "").strip().upper()
    if not text:
        return "UNKNOWN_ERROR"
    normalized = []
    last_was_sep = False
    for char in text:
        if char.isalnum():
            normalized.append(char)
            last_was_sep = False
            continue
        if not last_was_sep:
            normalized.append("_")
        last_was_sep = True
    output = "".join(normalized).strip("_")
    return output or "UNKNOWN_ERROR"


def _failure_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"reason": reason, "errorCode": _error_code_from_reason(reason)}
    if "plan_name" in extra and "planName" not in extra:
        extra["planName"] = extra.pop("plan_name")
    for key, value in extra.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        payload[key] = value
    return payload


def _should_publish_generated_artifact(task: dict[str, Any]) -> bool:
    files = task.get("_generated_files")
    if not isinstance(files, list):
        return False
    return bool(files)


def _resolve_agent_engine(engine: str | None) -> str:
    candidate = (engine or os.getenv("AGENT_ENGINE", "legacy")).strip().lower()
    return candidate if candidate in {"legacy", "langgraph"} else "legacy"


def _normalize_generation_target(task: dict[str, Any]) -> None:
    target = str(task.get("target", "")).strip().lower()
    if target:
        task["target"] = target
    export_mode = str(task.get("exportMode", "")).strip().lower()
    if export_mode:
        task["exportMode"] = export_mode


def _resolve_workspace(task: dict[str, Any]) -> Path:
    raw = str(task.get("workspacePath", "")).strip()
    if not raw or raw.lower() in {"none", "null", "undefined", "nil", "nan"}:
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
    raise FileNotFoundError("no generated files available for artifact packaging")


def _resolved_generation_target(task: dict[str, Any]) -> str:
    target = str(task.get("_generated_target") or task.get("target") or "").strip().lower()
    return target or "web"


def _generation_target_for_metrics(task: dict[str, Any]) -> str:
    target = str(task.get("_generated_target") or task.get("target") or "").strip().lower()
    if target:
        return target
    if _should_publish_generated_artifact(task):
        return _resolved_generation_target(task)
    return ""


def _build_artifact_ready_payload(
    task: dict[str, Any],
    bundle: ArtifactBundle,
    uploaded: dict[str, Any] | None,
    target: str,
    template_id: str,
    export_mode: str,
) -> dict[str, Any]:
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

    if target == "web":
        artifact["entryPath"] = "index.html"
        artifact["run"] = {
            "command": "python -m http.server 8000",
            "hints": [
                "Run the command in the extracted artifact directory.",
                "Open http://localhost:8000/index.html in a browser.",
            ],
        }
    elif target == "fullstack":
        artifact["entryPath"] = "frontend/index.html"
        artifact["run"] = {
            "command": "python backend/app.py",
            "hints": [
                "Install dependencies from requirements.txt first.",
                "Open frontend/index.html after the backend server is running.",
            ],
        }
    else:
        artifact["entryPath"] = "backend/app.py"
        artifact["run"] = {
            "command": "python backend/app.py",
            "hints": [
                "Install dependencies from requirements.txt first.",
                "Use the /health endpoint to confirm the service is running.",
            ],
        }

    payload["target"] = target
    payload["templateId"] = template_id
    payload["exportMode"] = export_mode
    return payload
