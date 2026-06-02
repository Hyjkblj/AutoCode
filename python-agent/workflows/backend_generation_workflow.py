"""
LangGraph workflow for backend_generation operations.

Implements the backend_generation intent as a proper LangGraph state machine
with four nodes:
    parse_request → generate_backend → validate_output → package_artifact

The output is compatible with the legacy backend_generation result format and
provides a structured result in ``metadata["backend_generation_result"]``.

**Validates: Requirements 8.3, 8.6**
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from generators.backend_generator import BackendGenerator
from generators.fix_loop import FixLoop
from generators.validation_gate import ValidationGate
from llm.llm_client import LLMClient
from utils.errors import LLMError, ValidationError
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
_STAGE_GENERATE_BACKEND = "generate_backend"
_STAGE_VALIDATE_OUTPUT = "validate_output"
_STAGE_PACKAGE_ARTIFACT = "package_artifact"


class BackendGenerationWorkflow(BaseWorkflow):
    """
    LangGraph workflow for the *backend_generation* intent.

    Graph topology
    --------------
    parse_request → generate_backend → validate_output → package_artifact → END

    Each node updates the shared :class:`~workflows.base_workflow.WorkflowState`
    and passes it to the next node.  The final state contains a
    ``metadata["backend_generation_result"]`` dict with the following structure::

        {
            "intent": "backend_generation",
            "result": "generated" | "failed",
            "success": bool,
            "framework": "flask" | "fastapi",
            "files": list[str],
            "executionPath": "langgraph",
        }

    Dependency injection
    --------------------
    ``BackendGenerator``, ``ValidationGate``, and ``FixLoop`` are injected via
    the constructor to enable testability without touching the filesystem or
    running real LLM calls.

    Error handling
    --------------
    - :class:`~utils.errors.LLMError` → retryable (handled by base class retry logic)
    - :class:`~utils.errors.ValidationError` → non-retryable (fails immediately)

    **Validates: Requirements 8.3, 8.6**
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        backend_generator: BackendGenerator | None = None,
        validation_gate: ValidationGate | None = None,
        fix_loop: FixLoop | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(llm_client=llm_client, **kwargs)
        self._backend_generator = backend_generator or BackendGenerator()
        self._validation_gate = validation_gate or ValidationGate()
        self._fix_loop = fix_loop or FixLoop()

    # ------------------------------------------------------------------
    # BaseWorkflow interface
    # ------------------------------------------------------------------

    def build_graph(self) -> StateGraph:
        """
        Construct the backend_generation workflow graph.

        Nodes
        -----
        parse_request
            Parses the incoming task to extract prompt, framework, and planName.
        generate_backend
            Calls :class:`~generators.backend_generator.BackendGenerator` to
            produce the backend source files.
        validate_output
            Calls :class:`~generators.validation_gate.ValidationGate` to verify
            the generated code.  On failure, delegates to
            :class:`~generators.fix_loop.FixLoop` for automatic repair.
        package_artifact
            Packages the validated files and records the final result.

        Returns
        -------
        StateGraph
            Configured (not yet compiled) workflow graph.
        """
        graph = StateGraph(WorkflowState)

        graph.add_node(_STAGE_PARSE_REQUEST, self._parse_request_node)
        graph.add_node(_STAGE_GENERATE_BACKEND, self._generate_backend_node)
        graph.add_node(_STAGE_VALIDATE_OUTPUT, self._validate_output_node)
        graph.add_node(_STAGE_PACKAGE_ARTIFACT, self._package_artifact_node)

        graph.set_entry_point(_STAGE_PARSE_REQUEST)
        graph.add_edge(_STAGE_PARSE_REQUEST, _STAGE_GENERATE_BACKEND)
        graph.add_edge(_STAGE_GENERATE_BACKEND, _STAGE_VALIDATE_OUTPUT)
        graph.add_edge(_STAGE_VALIDATE_OUTPUT, _STAGE_PACKAGE_ARTIFACT)
        graph.add_edge(_STAGE_PACKAGE_ARTIFACT, END)

        return graph

    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        """
        Build the initial state for a backend_generation task.

        Parameters
        ----------
        task:
            Raw task dict.  Expected keys: ``task_id``, ``prompt``,
            ``framework`` (optional, defaults to "flask"),
            ``planName`` (optional).

        Returns
        -------
        WorkflowState
            Populated initial state with intent="backend_generation" and
            metadata containing the prompt, framework, and planName.
        """
        return WorkflowState(
            task_id=str(task.get("task_id", "")),
            intent="backend_generation",
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
            "BackendGenerationWorkflow parse_request: task_id=%s framework=%s",
            state.get("task_id"),
            framework,
        )
        return updated  # type: ignore[return-value]

    def _generate_backend_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 2: generate_backend

        Calls :class:`~generators.backend_generator.BackendGenerator` to
        produce the backend source files.  Stores the generated files in
        ``state["code"]`` and ``state["plan"]["files"]``.

        Raises
        ------
        LLMError
            When the generator raises an unexpected exception (retryable).
        """
        updated = dict(state)
        updated["stage"] = _STAGE_GENERATE_BACKEND

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan: dict[str, Any] = dict(state.get("plan") or {})
        prompt = metadata.get("prompt", "")

        try:
            result = self._backend_generator.generate(prompt)
            file_names = list(result.files.keys())
            plan["files"] = file_names
            plan["generated_files"] = result.files
            updated["plan"] = plan
            updated["code"] = dict(result.files)
            metadata["generation_complete"] = True
            metadata["used_fallback"] = result.used_fallback
            updated["metadata"] = metadata

            logger.debug(
                "BackendGenerationWorkflow generate_backend: task_id=%s files=%d",
                state.get("task_id"),
                len(file_names),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "BackendGenerationWorkflow generate_backend failed: task_id=%s error=%s",
                state.get("task_id"),
                exc,
            )
            # Wrap in LLMError so base class retry logic applies
            raise LLMError(str(exc), error_code="LLM_TIMEOUT") from exc

        return updated  # type: ignore[return-value]

    def _validate_output_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 3: validate_output

        Calls :class:`~generators.validation_gate.ValidationGate` to verify
        the generated code.  On failure, delegates to
        :class:`~generators.fix_loop.FixLoop` for automatic repair (up to 3
        iterations).

        Sets ``state["metadata"]["validation_passed"]`` to True/False.
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
                "BackendGenerationWorkflow validate_output: no generated files for task_id=%s",
                state.get("task_id"),
            )
            updated["plan"] = plan
            return updated  # type: ignore[return-value]

        # Write generated files to a temp workspace for validation
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            for rel_path, content in generated_files.items():
                dest = workspace / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            # Build a minimal task dict for the validators
            raw_task = metadata.get("raw_task") or {}
            validation_task = {
                **raw_task,
                "_generated_target": "backend",
                "target": "backend",
                "prompt": metadata.get("prompt", ""),
            }

            validation_result = self._validation_gate.validate(validation_task, workspace)

            if validation_result.ok:
                metadata["validation_passed"] = True
                logger.debug(
                    "BackendGenerationWorkflow validate_output: validation passed task_id=%s",
                    state.get("task_id"),
                )
            else:
                logger.info(
                    "BackendGenerationWorkflow validate_output: validation failed, "
                    "attempting fix_loop task_id=%s errors=%s",
                    state.get("task_id"),
                    validation_result.errors,
                )
                # Attempt automatic repair via FixLoop
                fix_result = self._fix_loop.fix_and_validate(validation_task, workspace)
                metadata["validation_passed"] = fix_result.success
                metadata["fix_loop_iterations"] = fix_result.iterations_used
                if not fix_result.success:
                    metadata["validation_errors"] = fix_result.final_errors
                    logger.warning(
                        "BackendGenerationWorkflow validate_output: fix_loop failed "
                        "task_id=%s final_errors=%s",
                        state.get("task_id"),
                        fix_result.final_errors,
                    )

        updated["metadata"] = metadata
        updated["plan"] = plan
        return updated  # type: ignore[return-value]

    def _package_artifact_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node 4: package_artifact

        Packages the validated files and records the final result in
        ``state["metadata"]["backend_generation_result"]``.
        """
        updated = dict(state)
        updated["stage"] = WORKFLOW_STAGE_COMPLETED

        metadata: dict[str, Any] = dict(state.get("metadata") or {})
        plan: dict[str, Any] = state.get("plan") or {}
        plan_name = metadata.get("plan_name", "") or "backend_generation_plan"
        framework = metadata.get("framework", "flask")
        file_names: list[str] = plan.get("files") or []
        validation_passed = metadata.get("validation_passed", False)

        success = validation_passed and bool(file_names)
        result_status = "generated" if success else "failed"

        # Build the backend_generation result payload
        backend_generation_result: dict[str, Any] = {
            "intent": "backend_generation",
            "result": result_status,
            "success": success,
            "framework": framework,
            "files": file_names,
            "executionPath": "langgraph",
            "planName": plan_name,
        }

        # Build memory record
        memory_record: dict[str, Any] = {
            "intent": "backend_generation",
            "planName": plan_name,
            "status": "done",
            "result": result_status,
            "executionPath": "langgraph",
        }

        metadata["backend_generation_result"] = backend_generation_result
        metadata["memory_record"] = memory_record
        updated["metadata"] = metadata

        logger.info(
            "BackendGenerationWorkflow package_artifact: task_id=%s result=%s files=%d",
            state.get("task_id"),
            result_status,
            len(file_names),
        )
        return updated  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public helper methods
    # ------------------------------------------------------------------

    def get_backend_generation_result(self, final_state: WorkflowState) -> dict[str, Any]:
        """
        Extract the backend_generation result from the final state.

        Parameters
        ----------
        final_state:
            The :class:`WorkflowState` returned by :meth:`run`.

        Returns
        -------
        dict[str, Any]
            Backend generation result dict with keys: intent, result, success,
            framework, files, executionPath.
        """
        metadata = final_state.get("metadata") or {}
        return dict(metadata.get("backend_generation_result") or {})

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
