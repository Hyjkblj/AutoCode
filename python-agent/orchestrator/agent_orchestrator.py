from __future__ import annotations

import os
from typing import Any

from agents.base_agent import BaseAgent
from agents.coder_agent import CoderAgent
from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from agents.reviewer_agent import ReviewResult, ReviewerAgent
from agents.tester_agent import TesterAgent, TesterResult
from client.control_plane_client import ControlPlaneClient
from tools.exec_tool import ExecResult, ExecTool


class AgentOrchestrator(BaseAgent):
    def __init__(
        self,
        intent_agent: IntentAgent | None = None,
        planner_agent: PlannerAgent | None = None,
        coder_agent: CoderAgent | None = None,
        reviewer_agent: ReviewerAgent | None = None,
        tester_agent: TesterAgent | None = None,
        exec_tool: ExecTool | None = None,
    ) -> None:
        super().__init__()
        self.intent_agent = intent_agent or IntentAgent()
        self.planner_agent = planner_agent or PlannerAgent()
        self.coder_agent = coder_agent or CoderAgent()
        self.reviewer_agent = reviewer_agent or ReviewerAgent()
        self.tester_agent = tester_agent or TesterAgent(exec_tool=exec_tool)
        self.exec_tool = exec_tool or ExecTool()

    def handle_task(self, task: dict[str, Any], client: ControlPlaneClient) -> None:
        prompt = str(task.get("prompt", "")).strip()
        decision = self.intent_agent.infer(prompt)
        self.publish_event(
            task,
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
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "PlannerAgent",
                "message": "Plan generated.",
                "planName": plan.plan_name,
                "steps": plan.steps,
            },
        )

        if decision.intent == "code_change":
            publisher = self._publisher(task, client)
            coded = self.coder_agent.execute(task, client, plan, publish_event=publisher)
            if not coded:
                return

            review = self.reviewer_agent.review(task, client, plan, publish_event=publisher)
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
                return

            test = self.tester_agent.execute(task, client, plan, publish_event=publisher)
            if test.success:
                self.publish_event(task, client, "TASK_DONE", _build_code_change_done_payload(plan.plan_name, review, test))
                return
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
            return

        if decision.intent in {"deploy", "test"}:
            self._execute_with_sandbox(task, client, decision.intent, prompt, plan.plan_name)
            return

        self.publish_event(
            task,
            client,
            "TASK_DONE",
            {
                "result": "planned",
                "planName": plan.plan_name,
                "steps": plan.steps,
            },
        )

    def _publisher(self, task: dict[str, Any], client: ControlPlaneClient):
        def _emit(payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
            self.publish_event(task, client, event_type, payload)

        return _emit

    def _execute_with_sandbox(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        intent: str,
        prompt: str,
        plan_name: str,
    ) -> None:
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
            return

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
            return
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


def _resolve_command(task: dict[str, Any], intent: str, prompt: str) -> str:
    explicit = str(task.get("command", "")).strip()
    if explicit:
        return explicit
    env_key = "MVP_DEPLOY_COMMAND" if intent == "deploy" else "MVP_TEST_COMMAND"
    env_command = os.getenv(env_key, "").strip()
    if env_command:
        return env_command
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


def _build_code_change_done_payload(plan_name: str, review: ReviewResult, test: TesterResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "result": "coded_reviewed_tested",
        "planName": plan_name,
        "reviewApproved": review.approved,
        "reviewSummary": review.summary,
        "testStatus": test.status,
        "testAttempts": test.attempts,
        "testRetries": test.retries,
    }
    if test.trace_id:
        payload["traceId"] = test.trace_id
    if test.run_id:
        payload["runId"] = test.run_id
    return payload


def _failure_reason(result: ExecResult) -> str:
    status = result.status.strip() if result.status else ""
    if status:
        return status
    if result.reason and result.reason.strip():
        return result.reason.strip()
    return "sandbox_exec_failed"
