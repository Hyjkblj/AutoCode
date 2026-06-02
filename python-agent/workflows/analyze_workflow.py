"""
LangGraph workflow for analyze operations.

Implements the analyze intent as a proper LangGraph state machine with
three nodes: intent_classification → code_analysis → result_formatting.

The output is compatible with the legacy analyze result format produced by
``AgentOrchestrator._build_langgraph_analyze_result``.

**Validates: Requirements 8.2, 8.4**
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from llm.llm_client import LLMClient
from workflows.base_workflow import (
    WORKFLOW_STAGE_COMPLETED,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_INIT,
    WORKFLOW_STAGE_RUNNING,
    BaseWorkflow,
    WorkflowState,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AnalyzeWorkflowState – extends WorkflowState with analyze-specific fields
# ---------------------------------------------------------------------------

# We reuse WorkflowState (total=False) and store analyze-specific data in
# the ``metadata`` and ``plan`` fields so the base class machinery works
# without modification.

_ANALYZE_STAGE_INTENT_CLASSIFICATION = "intent_classification"
_ANALYZE_STAGE_CODE_ANALYSIS = "code_analysis"
_ANALYZE_STAGE_RESULT_FORMATTING = "result_formatting"


class AnalyzeWorkflow(BaseWorkflow):
    """
    LangGraph workflow for the *analyze* intent.

    Graph topology
    --------------
    intent_classification → code_analysis → result_formatting → END

    Each node updates the shared :class:`~workflows.base_workflow.WorkflowState`
    and passes it to the next node.  The final state contains a
    ``metadata["analyze_result"]`` dict that is compatible with the legacy
    ``AgentOrchestrator._build_langgraph_analyze_result`` output format.

    **Validates: Requirements 8.2**
    """

    def build_graph(self) -> StateGraph:
        """
        Construct the analyze workflow graph.

        Nodes
        -----
        intent_classification
            Classifies the task intent and extracts key parameters.
        code_analysis
            Performs the actual analysis using the LLM.
        result_formatting
            Formats the result into the legacy-compatible output structure.

        Returns
        -------
        StateGraph
            Configured (not yet compiled) workflow graph.
        """
        graph = StateGraph(WorkflowState)

        graph.add_node(_ANALYZE_STAGE_INTENT_CLASSIFICATION, self._intent_classification_node)
        graph.add_node(_ANALYZE_STAGE_CODE_ANALYSIS, self._code_analysis_node)
        graph.add_node(_ANALYZE_STAGE_RESULT_FORMATTING, self._result_formatting_node)

        graph.set_entry_point(_ANALYZE_STAGE_INTENT_CLASSIFICATION)
        graph.add_edge(_ANALYZE_STAGE_INTENT_CLASSIFICATION, _ANALYZE_STAGE_CODE_ANALYSIS)
        graph.add_edge(_ANALYZE_STAGE_CODE_ANALYSIS, _ANALYZE_STAGE_RESULT_FORMATTING)
        graph.add_edge(_ANALYZE_STAGE_RESULT_FORMATTING, END)

        return graph

    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        """
        Build the initial state for an analyze task.

        Parameters
        ----------
        task:
            Raw task dict.  Expected keys: ``task_id``, ``prompt``,
            ``planName`` (optional).

        Returns
        -------
        WorkflowState
            Populated initial state.
        """
        return WorkflowState(
            task_id=str(task.get("task_id", "")),
            intent="analyze",
            plan={},
            code={},
            errors=[],
            metadata={
                "prompt": str(task.get("prompt", "")).strip(),
                "plan_name": str(task.get("planName", "")).strip(),
                "raw_task": task,
            },
            stage=WORKFLOW_STAGE_INIT,
            retry_count=0,
        )

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    def _intent_classification_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 1: intent_classification

        Classifies the task intent and extracts parameters needed for
        subsequent analysis.  Updates ``state["intent"]`` and enriches
        ``state["metadata"]`` with classification details.
        """
        updated = dict(state)
        updated["stage"] = _ANALYZE_STAGE_INTENT_CLASSIFICATION

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        prompt = metadata.get("prompt", "")

        # Classify intent – for analyze operations the intent is always
        # "analyze", but we extract sub-intent from the prompt.
        sub_intent = "general_analysis"
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in ("test", "spec", "coverage")):
            sub_intent = "test_analysis"
        elif any(kw in prompt_lower for kw in ("backend", "api", "route", "endpoint")):
            sub_intent = "backend_analysis"
        elif any(kw in prompt_lower for kw in ("frontend", "ui", "html", "css")):
            sub_intent = "frontend_analysis"
        elif any(kw in prompt_lower for kw in ("security", "auth", "permission")):
            sub_intent = "security_analysis"

        metadata["sub_intent"] = sub_intent
        metadata["classified"] = True
        updated["metadata"] = metadata
        updated["intent"] = "analyze"

        logger.debug(
            "AnalyzeWorkflow intent_classification: task_id=%s sub_intent=%s",
            state.get("task_id"),
            sub_intent,
        )
        return updated  # type: ignore[return-value]

    def _code_analysis_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 2: code_analysis

        Performs the core analysis using the LLM client.  Stores the raw
        analysis output in ``state["metadata"]["analysis_output"]``.
        """
        updated = dict(state)
        updated["stage"] = _ANALYZE_STAGE_CODE_ANALYSIS

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        prompt = metadata.get("prompt", "")
        sub_intent = metadata.get("sub_intent", "general_analysis")

        analysis_output: dict[str, Any] = {
            "sub_intent": sub_intent,
            "prompt": prompt,
            "steps": [],
            "summary": "",
        }

        if prompt:
            try:
                system_prompt = (
                    "You are a code analysis assistant. "
                    "Analyze the given task and provide a structured plan with steps. "
                    "Respond with a brief summary and a list of action steps."
                )
                llm_response = self.llm_client.generate(
                    f"Analyze this task and provide steps:\n{prompt}",
                    system_prompt=system_prompt,
                )
                analysis_output["summary"] = llm_response
                # Extract steps from the response (simple heuristic)
                lines = [ln.strip() for ln in llm_response.splitlines() if ln.strip()]
                steps = [
                    ln.lstrip("0123456789.-) ").strip()
                    for ln in lines
                    if ln and (ln[0].isdigit() or ln.startswith("-") or ln.startswith("*"))
                ]
                analysis_output["steps"] = steps or lines[:5]
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "AnalyzeWorkflow code_analysis LLM call failed: task_id=%s error=%s",
                    state.get("task_id"),
                    exc,
                )
                analysis_output["summary"] = f"Analysis pending: {prompt[:100]}"
                analysis_output["steps"] = [f"Analyze: {prompt[:80]}"]
                analysis_output["llm_error"] = str(exc)

        metadata["analysis_output"] = analysis_output
        updated["metadata"] = metadata
        updated["plan"] = {
            "steps": analysis_output["steps"],
            "summary": analysis_output["summary"],
            "sub_intent": sub_intent,
        }

        logger.debug(
            "AnalyzeWorkflow code_analysis: task_id=%s steps_count=%d",
            state.get("task_id"),
            len(analysis_output["steps"]),
        )
        return updated  # type: ignore[return-value]

    def _result_formatting_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 3: result_formatting

        Formats the analysis result into the legacy-compatible output
        structure.  The result is stored in
        ``state["metadata"]["analyze_result"]`` and mirrors the format
        produced by ``AgentOrchestrator._build_langgraph_analyze_result``.
        """
        updated = dict(state)
        updated["stage"] = WORKFLOW_STAGE_COMPLETED

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan = state.get("plan") or {}
        plan_name = metadata.get("plan_name", "") or "analyze_plan"
        steps = plan.get("steps", [])

        # Build legacy-compatible result payload
        analyze_result: dict[str, Any] = {
            "result": "planned",
            "intent": "analyze",
            "planName": plan_name,
            "steps": steps,
            "executionPath": "langgraph",
            "summary": plan.get("summary", ""),
            "sub_intent": plan.get("sub_intent", "general_analysis"),
        }

        # Build legacy-compatible memory record
        memory_record: dict[str, Any] = {
            "intent": "analyze",
            "planName": plan_name,
            "status": "done",
            "result": "planned",
            "executionPath": "langgraph",
        }

        metadata["analyze_result"] = analyze_result
        metadata["memory_record"] = memory_record
        updated["metadata"] = metadata

        logger.info(
            "AnalyzeWorkflow result_formatting: task_id=%s plan_name=%s steps=%d",
            state.get("task_id"),
            plan_name,
            len(steps),
        )
        return updated  # type: ignore[return-value]

    def get_analyze_result(self, final_state: WorkflowState) -> dict[str, Any]:
        """
        Extract the legacy-compatible analyze result from the final state.

        Parameters
        ----------
        final_state:
            The :class:`WorkflowState` returned by :meth:`run`.

        Returns
        -------
        dict[str, Any]
            Analyze result dict compatible with the legacy format.
        """
        metadata = final_state.get("metadata") or {}
        return dict(metadata.get("analyze_result") or {})

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
