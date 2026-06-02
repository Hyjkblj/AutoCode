"""
LangGraph workflow for test operations.

Implements the test intent as a proper LangGraph state machine with
three nodes: test_planning → test_execution → result_collection.

The output is compatible with the legacy test result format produced by
``AgentOrchestrator._execute_langgraph_test``.

**Validates: Requirements 8.2, 8.4**
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.graph import StateGraph, END

from tools.exec_tool import ExecResult, ExecTool
from workflows.base_workflow import (
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
    WORKFLOW_STAGE_RUNNING,
    BaseWorkflow,
    WorkflowState,
)

logger = logging.getLogger(__name__)

_TEST_STAGE_PLANNING = "test_planning"
_TEST_STAGE_EXECUTION = "test_execution"
_TEST_STAGE_RESULT_COLLECTION = "result_collection"

_DEFAULT_TEST_COMMAND = "echo test_from_python_agent"


class TestWorkflow(BaseWorkflow):
    """
    LangGraph workflow for the *test* intent.

    Graph topology
    --------------
    test_planning → test_execution → result_collection → END

    Each node updates the shared :class:`~workflows.base_workflow.WorkflowState`
    and passes it to the next node.  The final state contains a
    ``metadata["test_result"]`` dict that is compatible with the legacy
    ``AgentOrchestrator._execute_langgraph_test`` output format.

    Parameters
    ----------
    exec_tool:
        Optional :class:`~tools.exec_tool.ExecTool` for Java Sandbox
        integration.  A default instance is created when *None*.
    llm_client:
        Optional LLM client (passed to :class:`~workflows.base_workflow.BaseWorkflow`).
    timeout_config:
        Optional timeout configuration.
    max_retries:
        Maximum retry attempts for transient errors.

    **Validates: Requirements 8.2**
    """

    def __init__(
        self,
        *,
        exec_tool: ExecTool | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._exec_tool = exec_tool

    @property
    def exec_tool(self) -> ExecTool:
        """Return the :class:`~tools.exec_tool.ExecTool` instance, creating one on first access."""
        if self._exec_tool is None:
            self._exec_tool = ExecTool()
        return self._exec_tool

    def build_graph(self) -> StateGraph:
        """
        Construct the test workflow graph.

        Nodes
        -----
        test_planning
            Determines the test command and strategy.
        test_execution
            Executes the test command via the Java Sandbox.
        result_collection
            Collects and formats the test result into the legacy-compatible
            output structure.

        Returns
        -------
        StateGraph
            Configured (not yet compiled) workflow graph.
        """
        graph = StateGraph(WorkflowState)

        graph.add_node(_TEST_STAGE_PLANNING, self._test_planning_node)
        graph.add_node(_TEST_STAGE_EXECUTION, self._test_execution_node)
        graph.add_node(_TEST_STAGE_RESULT_COLLECTION, self._result_collection_node)

        graph.set_entry_point(_TEST_STAGE_PLANNING)
        graph.add_edge(_TEST_STAGE_PLANNING, _TEST_STAGE_EXECUTION)
        graph.add_edge(_TEST_STAGE_EXECUTION, _TEST_STAGE_RESULT_COLLECTION)
        graph.add_edge(_TEST_STAGE_RESULT_COLLECTION, END)

        return graph

    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        """
        Build the initial state for a test task.

        Parameters
        ----------
        task:
            Raw task dict.  Expected keys: ``task_id``, ``prompt``,
            ``testCommand`` (optional), ``planName`` (optional).

        Returns
        -------
        WorkflowState
            Populated initial state.
        """
        return WorkflowState(
            task_id=str(task.get("task_id", "")),
            intent="test",
            plan={},
            code={},
            errors=[],
            metadata={
                "prompt": str(task.get("prompt", "")).strip(),
                "plan_name": str(task.get("planName", "")).strip(),
                "test_command": str(task.get("testCommand", "")).strip(),
                "raw_task": task,
            },
            stage=WORKFLOW_STAGE_INIT,
            retry_count=0,
        )

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    def _test_planning_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 1: test_planning

        Determines the test command to execute.  Checks (in order):
        1. ``metadata["test_command"]`` from the task
        2. ``MVP_TEST_COMMAND`` environment variable
        3. Default fallback command

        Updates ``state["plan"]`` with the resolved command and strategy.
        """
        updated = dict(state)
        updated["stage"] = _TEST_STAGE_PLANNING

        metadata: dict[str, Any] = dict(state.get("metadata") or {})

        # Resolve test command
        test_command = metadata.get("test_command", "").strip()
        if not test_command:
            test_command = os.getenv("MVP_TEST_COMMAND", "").strip()
        if not test_command:
            test_command = _DEFAULT_TEST_COMMAND

        metadata["resolved_test_command"] = test_command
        updated["metadata"] = metadata
        updated["plan"] = {
            "test_command": test_command,
            "plan_name": metadata.get("plan_name", "test_plan"),
            "strategy": "sandbox_execution",
        }

        logger.debug(
            "TestWorkflow test_planning: task_id=%s command=%s",
            state.get("task_id"),
            test_command,
        )
        return updated  # type: ignore[return-value]

    def _test_execution_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 2: test_execution

        Executes the test command via the Java Sandbox (ExecTool).
        Stores the raw :class:`~tools.exec_tool.ExecResult` data in
        ``state["metadata"]["exec_result"]``.
        """
        updated = dict(state)
        updated["stage"] = _TEST_STAGE_EXECUTION

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan = state.get("plan") or {}
        test_command = plan.get("test_command", _DEFAULT_TEST_COMMAND)
        raw_task: dict[str, Any] = metadata.get("raw_task") or {}
        prompt = metadata.get("prompt", "")

        exec_result_data: dict[str, Any] = {
            "ok": False,
            "status": "not_executed",
            "exit_code": None,
            "output": "",
            "retryable": False,
            "reason": None,
            "trace_id": None,
            "run_id": None,
            "command": test_command,
        }

        # Only attempt sandbox execution when a real task_id is available
        task_id = str(raw_task.get("taskId", "") or state.get("task_id", "")).strip()
        if task_id:
            try:
                exec_task = dict(raw_task)
                exec_task.setdefault("taskId", task_id)
                result: ExecResult = self.exec_tool.execute(
                    exec_task,
                    test_command,
                    prompt=prompt,
                    intent="test",
                )
                exec_result_data = {
                    "ok": result.ok,
                    "status": result.status,
                    "exit_code": result.exit_code,
                    "output": result.output,
                    "retryable": result.retryable,
                    "reason": result.reason,
                    "trace_id": result.trace_id,
                    "run_id": result.run_id,
                    "command": test_command,
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "TestWorkflow test_execution sandbox call failed: task_id=%s error=%s",
                    state.get("task_id"),
                    exc,
                )
                exec_result_data["status"] = "sandbox_request_failed"
                exec_result_data["reason"] = str(exc)
        else:
            logger.debug(
                "TestWorkflow test_execution: no task_id, skipping sandbox call"
            )

        metadata["exec_result"] = exec_result_data
        updated["metadata"] = metadata

        logger.debug(
            "TestWorkflow test_execution: task_id=%s ok=%s status=%s",
            state.get("task_id"),
            exec_result_data["ok"],
            exec_result_data["status"],
        )
        return updated  # type: ignore[return-value]

    def _result_collection_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 3: result_collection

        Collects the execution result and formats it into the
        legacy-compatible output structure.  The result is stored in
        ``state["metadata"]["test_result"]`` and mirrors the format
        produced by ``AgentOrchestrator._execute_langgraph_test``.
        """
        updated = dict(state)

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan = state.get("plan") or {}
        exec_result = metadata.get("exec_result") or {}
        plan_name = plan.get("plan_name", "") or metadata.get("plan_name", "test_plan")
        test_command = exec_result.get("command", plan.get("test_command", _DEFAULT_TEST_COMMAND))

        ok = bool(exec_result.get("ok", False))
        status = str(exec_result.get("status", "not_executed"))
        reason = exec_result.get("reason")
        trace_id = exec_result.get("trace_id")
        run_id = exec_result.get("run_id")

        if ok:
            updated["stage"] = WORKFLOW_STAGE_COMPLETED
            test_result: dict[str, Any] = {
                "result": "executed",
                "intent": "test",
                "planName": plan_name,
                "status": status,
                "command": test_command,
                "executionPath": "langgraph",
                "success": True,
            }
            if trace_id:
                test_result["traceId"] = trace_id
            if run_id:
                test_result["runId"] = run_id

            memory_record: dict[str, Any] = {
                "intent": "test",
                "planName": plan_name,
                "status": "done",
                "command": test_command,
                "result": "executed",
                "traceId": trace_id,
                "runId": run_id,
                "executionPath": "langgraph",
            }
        else:
            updated["stage"] = WORKFLOW_STAGE_FAILED
            error_reason = status or reason or "test_failed"
            test_result = {
                "result": "failed",
                "intent": "test",
                "planName": plan_name,
                "status": status,
                "command": test_command,
                "reason": error_reason,
                "detail": reason,
                "executionPath": "langgraph",
                "success": False,
            }
            memory_record = {
                "intent": "test",
                "planName": plan_name,
                "status": "failed",
                "reason": error_reason,
                "detail": reason,
                "command": test_command,
                "traceId": trace_id,
                "runId": run_id,
                "executionPath": "langgraph",
            }

        metadata["test_result"] = test_result
        metadata["memory_record"] = memory_record
        updated["metadata"] = metadata

        logger.info(
            "TestWorkflow result_collection: task_id=%s success=%s status=%s",
            state.get("task_id"),
            ok,
            status,
        )
        return updated  # type: ignore[return-value]

    def get_test_result(self, final_state: WorkflowState) -> dict[str, Any]:
        """
        Extract the legacy-compatible test result from the final state.

        Parameters
        ----------
        final_state:
            The :class:`WorkflowState` returned by :meth:`run`.

        Returns
        -------
        dict[str, Any]
            Test result dict compatible with the legacy format.
        """
        metadata = final_state.get("metadata") or {}
        return dict(metadata.get("test_result") or {})

    def get_memory_record(self, final_state: WorkflowState) -> dict[str, Any]:
        """
        Extract the legacy-compatible memory record from the final state.

        Parameters
        ----------
        final_state:
            The :class:`WorkflowState` returned by :meth:`run`.

        Returns
        -------
        dict[str, Any]
            Memory record dict compatible with the legacy format.
        """
        metadata = final_state.get("metadata") or {}
        return dict(metadata.get("memory_record") or {})
