"""
LangGraph workflow for fullstack_generation operations.

Implements the fullstack_generation intent as a proper LangGraph state machine
with four nodes:
    parse_request → generate_fullstack → validate_output → package_artifact

The output is compatible with the legacy fullstack_generation result format and
provides a structured result in ``metadata["fullstack_generation_result"]``.

**Validates: Requirements 8.3**
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from generators.fullstack_generator import FullstackGenerator
from generators.validation_gate import ValidationGate
from llm.llm_client import LLMClient
from utils.errors import LLMError
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
# Stage name constants
# ---------------------------------------------------------------------------

_STAGE_PARSE_REQUEST = "parse_request"
_STAGE_GENERATE_FULLSTACK = "generate_fullstack"
_STAGE_VALIDATE_OUTPUT = "validate_output"
_STAGE_PACKAGE_ARTIFACT = "package_artifact"

# ---------------------------------------------------------------------------
# File classification helpers
# ---------------------------------------------------------------------------

_FRONTEND_PREFIXES = ("frontend/",)
_BACKEND_PREFIXES = ("backend/",)


def _classify_files(
    file_names: list[str],
) -> tuple[list[str], list[str]]:
    """
    Split a list of file names into frontend and backend lists.

    Files under ``frontend/`` are classified as frontend; files under
    ``backend/`` are classified as backend.  All other files (e.g.
    ``requirements.txt``, ``docker-compose.yml``) are included in the
    backend list for convenience.

    Returns
    -------
    tuple[list[str], list[str]]
        ``(frontend_files, backend_files)``
    """
    frontend: list[str] = []
    backend: list[str] = []
    for name in file_names:
        if any(name.startswith(prefix) for prefix in _FRONTEND_PREFIXES):
            frontend.append(name)
        else:
            backend.append(name)
    return frontend, backend


class FullstackWorkflow(BaseWorkflow):
    """
    LangGraph workflow for the *fullstack_generation* intent.

    Graph topology
    --------------
    parse_request → generate_fullstack → validate_output → package_artifact → END

    Each node updates the shared :class:`~workflows.base_workflow.WorkflowState`
    and passes it to the next node.  The final state contains a
    ``metadata["fullstack_generation_result"]`` dict with the following
    structure::

        {
            "intent": "fullstack_generation",
            "result": "generated" | "failed",
            "success": bool,
            "framework": "flask" | "fastapi",
            "frontend_files": list[str],
            "backend_files": list[str],
            "all_files": list[str],
            "executionPath": "langgraph",
        }

    Dependency injection
    --------------------
    ``FullstackGenerator`` is injected via the constructor to enable
    testability without touching the filesystem or running real LLM calls.

    Error handling
    --------------
    - :class:`~utils.errors.LLMError` → retryable (handled by base class retry logic)

    **Validates: Requirements 8.3**
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        fullstack_generator: FullstackGenerator | None = None,
        validation_gate: ValidationGate | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(llm_client=llm_client, **kwargs)
        self._fullstack_generator = fullstack_generator or FullstackGenerator()
        self._validation_gate = validation_gate or ValidationGate()

    # ------------------------------------------------------------------
    # BaseWorkflow interface
    # ------------------------------------------------------------------

    def build_graph(self) -> StateGraph:
        """
        Construct the fullstack_generation workflow graph.

        Nodes
        -----
        parse_request
            Parses the incoming task to extract prompt, framework, and planName.
        generate_fullstack
            Calls :class:`~generators.fullstack_generator.FullstackGenerator`
            to produce the combined frontend and backend source files.
        validate_output
            Validates that the generated output contains both frontend and
            backend files.
        package_artifact
            Packages the validated files and records the final result.

        Returns
        -------
        StateGraph
            Configured (not yet compiled) workflow graph.
        """
        graph = StateGraph(WorkflowState)

        graph.add_node(_STAGE_PARSE_REQUEST, self._parse_request_node)
        graph.add_node(_STAGE_GENERATE_FULLSTACK, self._generate_fullstack_node)
        graph.add_node(_STAGE_VALIDATE_OUTPUT, self._validate_output_node)
        graph.add_node(_STAGE_PACKAGE_ARTIFACT, self._package_artifact_node)

        graph.set_entry_point(_STAGE_PARSE_REQUEST)
        graph.add_edge(_STAGE_PARSE_REQUEST, _STAGE_GENERATE_FULLSTACK)
        graph.add_edge(_STAGE_GENERATE_FULLSTACK, _STAGE_VALIDATE_OUTPUT)
        graph.add_edge(_STAGE_VALIDATE_OUTPUT, _STAGE_PACKAGE_ARTIFACT)
        graph.add_edge(_STAGE_PACKAGE_ARTIFACT, END)

        return graph

    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        """
        Build the initial state for a fullstack_generation task.

        Parameters
        ----------
        task:
            Raw task dict.  Expected keys: ``task_id``, ``prompt``,
            ``framework`` (optional, defaults to "flask"),
            ``planName`` (optional).

        Returns
        -------
        WorkflowState
            Populated initial state with intent="fullstack_generation" and
            metadata containing the prompt, framework, and planName.
        """
        return WorkflowState(
            task_id=str(task.get("task_id", "")),
            intent="fullstack_generation",
            plan={},
            code={},
            errors=[],
            metadata={
                "prompt": str(task.get("prompt", "")).strip(),
                "framework": str(task.get("framework", "flask")).strip().lower() or "flask",
                "plan_name": str(task.get("planName", "")).strip(),
                "raw_task": task,
            },
            stage=WORKFLOW_STAGE_INIT,
            retry_count=0,
        )

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    def _parse_request_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 1: parse_request

        Parses the incoming task to extract the generation request details.
        Enriches ``state["metadata"]`` with classification details and
        populates ``state["plan"]`` with the parsed request.
        """
        updated = dict(state)
        updated["stage"] = _STAGE_PARSE_REQUEST

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        prompt = metadata.get("prompt", "")
        framework = metadata.get("framework", "flask")

        # Normalise framework value
        if framework not in ("flask", "fastapi"):
            framework = "flask"
            metadata["framework"] = framework

        metadata["parsed"] = True
        updated["metadata"] = metadata
        updated["plan"] = {
            "prompt": prompt,
            "framework": framework,
            "files": [],
        }

        logger.debug(
            "FullstackWorkflow parse_request: task_id=%s framework=%s",
            state.get("task_id"),
            framework,
        )
        return updated  # type: ignore[return-value]

    def _generate_fullstack_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 2: generate_fullstack

        Calls :class:`~generators.fullstack_generator.FullstackGenerator` to
        produce the combined frontend and backend source files.  Stores the
        generated files in ``state["code"]`` and ``state["plan"]["files"]``.

        Raises
        ------
        LLMError
            When the generator raises an unexpected exception (retryable).
        """
        updated = dict(state)
        updated["stage"] = _STAGE_GENERATE_FULLSTACK

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan: dict[str, Any] = dict(state.get("plan") or {})
        prompt = metadata.get("prompt", "")
        raw_task = metadata.get("raw_task") or {}

        try:
            result = self._fullstack_generator.generate(prompt, task=raw_task)
            file_names = list(result.files.keys())
            plan["files"] = file_names
            plan["generated_files"] = result.files
            updated["plan"] = plan
            updated["code"] = dict(result.files)
            metadata["generation_complete"] = True
            metadata["used_fallback"] = result.used_fallback
            updated["metadata"] = metadata

            logger.debug(
                "FullstackWorkflow generate_fullstack: task_id=%s files=%d",
                state.get("task_id"),
                len(file_names),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "FullstackWorkflow generate_fullstack failed: task_id=%s error=%s",
                state.get("task_id"),
                exc,
            )
            # Wrap in LLMError so base class retry logic applies
            raise LLMError(str(exc), error_code="LLM_TIMEOUT") from exc

        return updated  # type: ignore[return-value]

    def _validate_output_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 3: validate_output

        Validates that the generated output contains both frontend and backend
        files.  Sets ``state["metadata"]["validation_passed"]`` to True/False.
        """
        updated = dict(state)
        updated["stage"] = _STAGE_VALIDATE_OUTPUT

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan: dict[str, Any] = state.get("plan") or {}
        generated_files: dict[str, str] = plan.get("generated_files") or {}

        if not generated_files:
            metadata["validation_passed"] = False
            updated["metadata"] = metadata
            logger.warning(
                "FullstackWorkflow validate_output: no generated files for task_id=%s",
                state.get("task_id"),
            )
            updated["plan"] = plan
            return updated  # type: ignore[return-value]

        file_names = list(generated_files.keys())
        frontend_files, backend_files = _classify_files(file_names)

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            for rel_path, content in generated_files.items():
                dest = workspace / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            raw_task = metadata.get("raw_task") or {}
            validation_task = {
                **raw_task,
                "_generated_target": "fullstack",
                "target": "fullstack",
                "prompt": metadata.get("prompt", ""),
            }
            validation_result = self._validation_gate.validate(validation_task, workspace)

        validation_passed = validation_result.ok

        metadata["validation_passed"] = validation_passed
        metadata["frontend_files"] = frontend_files
        metadata["backend_files"] = backend_files
        if not validation_passed:
            metadata["validation_errors"] = validation_result.errors

        if not validation_passed:
            logger.warning(
                "FullstackWorkflow validate_output: validation failed task_id=%s errors=%s",
                state.get("task_id"),
                validation_result.errors,
            )
        else:
            logger.debug(
                "FullstackWorkflow validate_output: validation passed task_id=%s "
                "frontend=%d backend=%d",
                state.get("task_id"),
                len(frontend_files),
                len(backend_files),
            )

        updated["metadata"] = metadata
        updated["plan"] = plan
        return updated  # type: ignore[return-value]

    def _package_artifact_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 4: package_artifact

        Packages the validated files and records the final result in
        ``state["metadata"]["fullstack_generation_result"]``.
        """
        updated = dict(state)
        updated["stage"] = WORKFLOW_STAGE_COMPLETED

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan: dict[str, Any] = state.get("plan") or {}
        plan_name = metadata.get("plan_name", "") or "fullstack_generation_plan"
        framework = metadata.get("framework", "flask")
        all_files: list[str] = plan.get("files") or []
        validation_passed = metadata.get("validation_passed", False)
        frontend_files: list[str] = metadata.get("frontend_files") or []
        backend_files: list[str] = metadata.get("backend_files") or []

        # If validation_passed is False but we have files, re-classify from plan
        if not validation_passed and all_files and not frontend_files and not backend_files:
            frontend_files, backend_files = _classify_files(all_files)

        success = validation_passed and bool(all_files)
        result_status = "generated" if success else "failed"

        # Build the fullstack_generation result payload
        fullstack_generation_result: dict[str, Any] = {
            "intent": "fullstack_generation",
            "result": result_status,
            "success": success,
            "framework": framework,
            "frontend_files": frontend_files,
            "backend_files": backend_files,
            "all_files": all_files,
            "executionPath": "langgraph",
            "planName": plan_name,
        }

        # Build memory record
        memory_record: dict[str, Any] = {
            "intent": "fullstack_generation",
            "planName": plan_name,
            "status": "done",
            "result": result_status,
            "executionPath": "langgraph",
        }

        metadata["fullstack_generation_result"] = fullstack_generation_result
        metadata["memory_record"] = memory_record
        updated["metadata"] = metadata

        logger.info(
            "FullstackWorkflow package_artifact: task_id=%s result=%s "
            "frontend=%d backend=%d total=%d",
            state.get("task_id"),
            result_status,
            len(frontend_files),
            len(backend_files),
            len(all_files),
        )
        return updated  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public helper methods
    # ------------------------------------------------------------------

    def get_fullstack_generation_result(self, final_state: WorkflowState) -> dict[str, Any]:
        """
        Extract the fullstack_generation result from the final state.

        Parameters
        ----------
        final_state:
            The :class:`WorkflowState` returned by :meth:`run`.

        Returns
        -------
        dict[str, Any]
            Fullstack generation result dict with keys: intent, result, success,
            framework, frontend_files, backend_files, all_files, executionPath.
        """
        metadata = final_state.get("metadata") or {}
        return dict(metadata.get("fullstack_generation_result") or {})

    def get_memory_record(self, final_state: WorkflowState) -> dict[str, Any]:
        """
        Extract the memory record from the final state.

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
