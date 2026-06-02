"""
LangGraph workflow base classes for the Python Agent.

Provides the foundational infrastructure for building LangGraph-based
orchestration workflows, including:
- WorkflowState TypedDict for shared state across graph nodes
- BaseWorkflow abstract class with LangGraph StateGraph integration
- Error handling and retry logic using existing error types
- Timeout enforcement using existing timeout configuration
- Integration with existing LangChain model adapters (LLMClient)

**Validates: Requirements 8.5, 8.6**
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from config.timeout_config import (
    DEFAULT_TIMEOUT_CONFIG,
    TimeoutConfig,
    stage_timeout,
)
from llm.llm_client import LLMClient
from utils.errors import (
    AgentError,
    LLMError,
    PluginError,
    ProtocolError,
    SandboxError,
    ValidationError,
    categorize_exception,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workflow stage constants
# ---------------------------------------------------------------------------

WORKFLOW_STAGE_INIT = "init"
WORKFLOW_STAGE_RUNNING = "running"
WORKFLOW_STAGE_COMPLETED = "completed"
WORKFLOW_STAGE_FAILED = "failed"
WORKFLOW_STAGE_RETRYING = "retrying"

#: Maximum number of automatic retries for transient errors.
MAX_RETRY_COUNT: int = 3


# ---------------------------------------------------------------------------
# WorkflowState TypedDict
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict, total=False):
    """
    Shared state dictionary passed between LangGraph nodes.

    All fields are optional (total=False) so individual nodes can update
    only the fields they are responsible for.  The orchestrator populates
    the required fields before the graph starts.

    Fields
    ------
    task_id : str
        Unique identifier for the task being processed.
    intent : str
        Classified intent of the task (e.g. "backend_generation", "analyze").
    plan : dict[str, Any]
        Structured plan produced by the planner stage.
    code : dict[str, str]
        Generated code artefacts keyed by filename.
    errors : list[dict[str, Any]]
        Accumulated error records from all stages.
    metadata : dict[str, Any]
        Arbitrary metadata (trace IDs, timestamps, custom flags, etc.).
    stage : str
        Current workflow stage name (one of the WORKFLOW_STAGE_* constants).
    retry_count : int
        Number of retry attempts made so far for the current operation.
    """

    task_id: str
    intent: str
    plan: dict[str, Any]
    code: dict[str, str]
    errors: list[dict[str, Any]]
    metadata: dict[str, Any]
    stage: str
    retry_count: int


# ---------------------------------------------------------------------------
# Error categorization helpers
# ---------------------------------------------------------------------------

#: Error types that are safe to retry automatically.
_RETRYABLE_ERROR_TYPES: tuple[type[AgentError], ...] = (
    LLMError,
    SandboxError,
    ProtocolError,
)

#: Error types that should never be retried.
_NON_RETRYABLE_ERROR_TYPES: tuple[type[AgentError], ...] = (
    ValidationError,
    PluginError,
)


def _is_retryable_error(error: Exception) -> bool:
    """
    Return True if *error* is a transient error that can be retried.

    Uses the existing error classification from ``utils.errors`` and
    additionally checks the ``retryable`` attribute on :class:`AgentError`
    instances.
    """
    if isinstance(error, AgentError):
        return error.retryable
    # For non-AgentError exceptions, check if they wrap a known retryable type
    error_class = categorize_exception(error)
    if error_class is not None:
        # Instantiate a temporary instance to check retryability
        return error_class("").retryable
    return False


def _build_error_record(error: Exception, stage: str, task_id: str = "") -> dict[str, Any]:
    """
    Build a structured error record for inclusion in WorkflowState.errors.

    Parameters
    ----------
    error:
        The exception that was raised.
    stage:
        The workflow stage where the error occurred.
    task_id:
        Optional task identifier for correlation.

    Returns
    -------
    dict[str, Any]
        Structured error record with type, message, stage, retryable flag,
        and timestamp.
    """
    if isinstance(error, AgentError):
        record = error.to_dict()
    else:
        record = {
            "errorType": type(error).__name__,
            "reason": "unexpected_error",
            "detail": str(error),
            "errorCode": "",
            "description": str(error),
            "retryable": False,
        }
    record["stage"] = stage
    record["taskId"] = task_id
    record["timestamp"] = time.time()
    return record


# ---------------------------------------------------------------------------
# BaseWorkflow abstract class
# ---------------------------------------------------------------------------

class BaseWorkflow(ABC):
    """
    Abstract base class for LangGraph-based orchestration workflows.

    Subclasses must implement :meth:`build_graph` and
    :meth:`get_initial_state` to define the workflow topology and the
    initial state for a given task.

    The class provides:
    - LangGraph :class:`StateGraph` construction via :meth:`build_graph`
    - Unified :meth:`run` entry point with timeout enforcement
    - Error handling via :meth:`_handle_error`
    - Retry logic via :meth:`_should_retry`
    - Integration with :class:`~llm.llm_client.LLMClient` for LLM calls

    Parameters
    ----------
    llm_client:
        Optional :class:`~llm.llm_client.LLMClient` instance.  When
        *None* a default client is created on first use.
    timeout_config:
        Optional :class:`~config.timeout_config.TimeoutConfig`.  Defaults
        to :data:`~config.timeout_config.DEFAULT_TIMEOUT_CONFIG`.
    max_retries:
        Maximum number of automatic retry attempts for transient errors.
        Defaults to :data:`MAX_RETRY_COUNT`.

    **Validates: Requirements 8.5**
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        timeout_config: TimeoutConfig | None = None,
        max_retries: int = MAX_RETRY_COUNT,
    ) -> None:
        self._llm_client = llm_client
        self._timeout_config: TimeoutConfig = timeout_config or DEFAULT_TIMEOUT_CONFIG
        self._max_retries: int = max(0, int(max_retries))
        self._graph: StateGraph | None = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        Construct and return the LangGraph :class:`StateGraph` for this
        workflow.

        Subclasses must define all nodes and edges here.  The returned
        graph should **not** be compiled yet; :meth:`run` handles
        compilation.

        Returns
        -------
        StateGraph
            The configured (but not yet compiled) workflow graph.
        """

    @abstractmethod
    def get_initial_state(self, task: dict[str, Any]) -> WorkflowState:
        """
        Build the initial :class:`WorkflowState` for the given *task*.

        Parameters
        ----------
        task:
            Raw task dictionary as received from the control plane.

        Returns
        -------
        WorkflowState
            Fully populated initial state ready for graph execution.
        """

    # ------------------------------------------------------------------
    # LLM adapter integration
    # ------------------------------------------------------------------

    @property
    def llm_client(self) -> LLMClient:
        """
        Return the :class:`~llm.llm_client.LLMClient` instance.

        Creates a default client on first access if none was provided at
        construction time.

        **Validates: Requirements 8.5** – integrates with existing LangChain
        model adapters.
        """
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    # ------------------------------------------------------------------
    # Public run interface
    # ------------------------------------------------------------------

    def run(self, task: dict[str, Any]) -> WorkflowState:
        """
        Execute the workflow for the given *task*.

        Builds (and caches) the compiled graph, initialises the state,
        then invokes the graph.  Timeout enforcement is applied at the
        workflow level using the ``max_task_execution_seconds`` from the
        configured :class:`~config.timeout_config.TimeoutConfig`.

        Parameters
        ----------
        task:
            Raw task dictionary.  Must contain at least a ``task_id`` key.

        Returns
        -------
        WorkflowState
            Final state after the workflow completes (or fails).

        Raises
        ------
        AgentError
            Re-raised after exhausting all retry attempts.
        Exception
            Any unexpected exception that is not an :class:`AgentError`.

        **Validates: Requirements 8.5, 8.6**
        """
        task_id = str(task.get("task_id", ""))
        logger.info("Starting workflow %s for task_id=%s", type(self).__name__, task_id)

        # Build and compile the graph once per workflow instance
        if self._graph is None:
            self._graph = self.build_graph()

        compiled = self._graph.compile()
        state = self.get_initial_state(task)

        # Enforce the global maximum execution timeout
        max_timeout = self._timeout_config.max_task_execution_seconds
        with stage_timeout("coder", max_timeout, task_id=task_id):
            final_state = self._run_with_retry(compiled, state, task_id)

        return final_state

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _handle_error(
        self,
        state: WorkflowState,
        error: Exception,
        *,
        stage: str = "unknown",
    ) -> WorkflowState:
        """
        Record *error* in *state* and update the workflow stage.

        Categorises the error using the existing error taxonomy from
        ``utils.errors``, builds a structured error record, and appends
        it to ``state["errors"]``.  Sets ``state["stage"]`` to
        ``WORKFLOW_STAGE_FAILED`` unless the error is retryable and the
        retry limit has not been reached.

        Parameters
        ----------
        state:
            Current workflow state to update.
        error:
            The exception that was raised.
        stage:
            The workflow stage where the error occurred.

        Returns
        -------
        WorkflowState
            Updated state with the error recorded.

        **Validates: Requirements 8.6**
        """
        task_id = state.get("task_id", "")
        error_record = _build_error_record(error, stage=stage, task_id=task_id)

        # Ensure errors list exists
        errors: list[dict[str, Any]] = list(state.get("errors") or [])
        errors.append(error_record)

        updated: WorkflowState = dict(state)  # type: ignore[assignment]
        updated["errors"] = errors

        retryable = _is_retryable_error(error)
        retry_count = int(state.get("retry_count") or 0)

        if retryable and retry_count < self._max_retries:
            updated["stage"] = WORKFLOW_STAGE_RETRYING
            logger.warning(
                "Retryable error in workflow %s stage=%s task_id=%s retry=%d/%d: %s",
                type(self).__name__,
                stage,
                task_id,
                retry_count + 1,
                self._max_retries,
                error,
            )
        else:
            updated["stage"] = WORKFLOW_STAGE_FAILED
            logger.error(
                "Non-retryable error (or retries exhausted) in workflow %s "
                "stage=%s task_id=%s: %s",
                type(self).__name__,
                stage,
                task_id,
                error,
            )

        return updated

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _should_retry(self, state: WorkflowState) -> bool:
        """
        Return True if the workflow should retry the current operation.

        Checks that:
        1. The current stage is :data:`WORKFLOW_STAGE_RETRYING`.
        2. The ``retry_count`` has not reached ``max_retries``.
        3. The most recent error is classified as retryable.

        Parameters
        ----------
        state:
            Current workflow state.

        Returns
        -------
        bool
            True if a retry should be attempted.

        **Validates: Requirements 8.6**
        """
        if state.get("stage") != WORKFLOW_STAGE_RETRYING:
            return False

        retry_count = int(state.get("retry_count") or 0)
        if retry_count >= self._max_retries:
            return False

        errors: list[dict[str, Any]] = state.get("errors") or []
        if not errors:
            return False

        last_error = errors[-1]
        return bool(last_error.get("retryable", False))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_with_retry(
        self,
        compiled_graph: Any,
        initial_state: WorkflowState,
        task_id: str,
    ) -> WorkflowState:
        """
        Invoke *compiled_graph* with retry logic for transient failures.

        Parameters
        ----------
        compiled_graph:
            The compiled LangGraph graph object.
        initial_state:
            Initial workflow state.
        task_id:
            Task identifier for logging.

        Returns
        -------
        WorkflowState
            Final state after successful execution or exhausted retries.
        """
        state = initial_state
        attempt = 0

        while True:
            try:
                result = compiled_graph.invoke(state)
                # LangGraph returns the final state dict
                final_state: WorkflowState = result  # type: ignore[assignment]
                logger.info(
                    "Workflow %s completed successfully for task_id=%s after %d attempt(s)",
                    type(self).__name__,
                    task_id,
                    attempt + 1,
                )
                return final_state

            except Exception as exc:  # noqa: BLE001
                updated_state = self._handle_error(state, exc, stage=state.get("stage", "unknown"))

                if self._should_retry(updated_state):
                    attempt += 1
                    retry_count = int(updated_state.get("retry_count") or 0)
                    updated_state["retry_count"] = retry_count + 1
                    state = updated_state
                    logger.info(
                        "Retrying workflow %s for task_id=%s (attempt %d/%d)",
                        type(self).__name__,
                        task_id,
                        attempt + 1,
                        self._max_retries + 1,
                    )
                    continue

                # No more retries — return the failed state
                return updated_state
