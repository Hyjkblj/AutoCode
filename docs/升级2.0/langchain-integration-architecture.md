# LangChain Integration Architecture

**Version:** 1.0  
**Date:** 2026-05  
**Scope:** Python Agent — Unified LangChain Adapter Layer  
**Validates: Requirements 8.5, 8.6**

---

## 1. Overview

This document defines the integration architecture for LangChain within the Python Agent. LangChain serves as the **capability layer** — providing unified model access, tool adapters, prompt templates, and structured output parsing — while LangGraph provides the **execution layer** (state machine, node orchestration, checkpointing).

The architecture ensures that:
- All LLM calls go through a single, consistent adapter regardless of provider
- Existing tools and plugins integrate with LangGraph workflows without modification
- LangGraph operation failures produce clear, categorized errors with fallback options
- The LangChain layer is independently testable and replaceable

---

## 2. Unified Model Adapter Layer

### 2.1 Design Rationale

The current `python-agent/llm/llm_client.py` wraps a single LLM provider with custom retry and timeout logic. As the system migrates to LangGraph, multiple nodes may call different models (e.g., a fast model for intent classification, a capable model for code generation). A unified adapter layer prevents duplicated retry/timeout logic and enables provider switching without touching workflow code.

**Requirement 8.5:** The LangGraph engine SHALL integrate with existing LangChain model and tool adapters.

### 2.2 Model Adapter Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangChain Model Adapter Layer                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  ModelAdapterFactory                     │   │
│  │  get_model(role: ModelRole) → BaseChatModel             │   │
│  └──────────────────────┬──────────────────────────────────┘   │
│                         │                                       │
│         ┌───────────────┼───────────────┐                       │
│         ▼               ▼               ▼                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ OpenAI      │ │ Anthropic   │ │ Local/Ollama│               │
│  │ Adapter     │ │ Adapter     │ │ Adapter     │               │
│  │ (ChatOpenAI)│ │(ChatAnthropic)│(ChatOllama) │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Reliability Wrapper                         │   │
│  │  - Retry with exponential backoff (max 3 attempts)      │   │
│  │  - Timeout enforcement per model role                   │   │
│  │  - Circuit breaker integration                          │   │
│  │  - Structured output parsing with fallback              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Model Role Definitions

Different nodes in the LangGraph workflow use models optimized for their task:

```python
# python-agent/llm/model_roles.py
from enum import Enum

class ModelRole(Enum):
    INTENT_CLASSIFICATION = "intent"      # Fast, low-cost: GPT-4o-mini or Claude Haiku
    PLANNING = "planning"                 # Balanced: GPT-4o or Claude Sonnet
    CODE_GENERATION = "code_gen"          # Capable: GPT-4o or Claude Opus
    CODE_REVIEW = "code_review"           # Balanced: GPT-4o or Claude Sonnet
    TEST_GENERATION = "test_gen"          # Balanced: GPT-4o or Claude Sonnet
    FIX_LOOP = "fix_loop"                 # Capable: GPT-4o or Claude Opus
```

### 2.4 Model Adapter Implementation

```python
# python-agent/llm/model_adapter.py
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .model_roles import ModelRole
from ..utils.circuit_breaker import CircuitBreaker
from ..config.timeout_config import STAGE_TIMEOUTS

# Model configuration per role
MODEL_CONFIG = {
    ModelRole.INTENT_CLASSIFICATION: {
        "openai": {"model": "gpt-4o-mini", "temperature": 0.0},
        "anthropic": {"model": "claude-haiku-20240307", "temperature": 0.0},
    },
    ModelRole.CODE_GENERATION: {
        "openai": {"model": "gpt-4o", "temperature": 0.2},
        "anthropic": {"model": "claude-opus-20240229", "temperature": 0.2},
    },
    # ... other roles
}

class ModelAdapterFactory:
    """
    Creates LangChain model instances for each workflow node role.
    Wraps models with retry, timeout, and circuit breaker logic.
    """

    def __init__(self):
        self._provider = os.getenv("LLM_PROVIDER", "openai")
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
        )

    def get_model(self, role: ModelRole) -> BaseChatModel:
        config = MODEL_CONFIG[role][self._provider]
        timeout = STAGE_TIMEOUTS.get(role.value, 60)

        if self._provider == "openai":
            base_model = ChatOpenAI(
                **config,
                request_timeout=timeout,
                max_retries=3,
            )
        elif self._provider == "anthropic":
            base_model = ChatAnthropic(
                **config,
                timeout=timeout,
                max_retries=3,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self._provider}")

        return self._wrap_with_circuit_breaker(base_model, role)

    def _wrap_with_circuit_breaker(
        self, model: BaseChatModel, role: ModelRole
    ) -> BaseChatModel:
        """Wraps model invoke with circuit breaker protection."""
        original_invoke = model.invoke

        def protected_invoke(input, **kwargs):
            return self._circuit_breaker.call(
                lambda: original_invoke(input, **kwargs),
                context={"role": role.value},
            )

        model.invoke = protected_invoke
        return model
```

---

## 3. Tool Adapter Layer

### 3.1 Design Rationale

The Python Agent has existing tools (sandbox execution, file I/O, validation) that must be accessible from LangGraph nodes. LangChain's `@tool` decorator and `BaseTool` interface provide a standard way to expose these as LangGraph-compatible tools without rewriting them.

### 3.2 Tool Adapter Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangChain Tool Adapter Layer                  │
│                                                                 │
│  Existing Python Agent Tools:                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Java Sandbox │ │ File I/O     │ │ Validation Gate      │    │
│  │ Executor     │ │ Tools        │ │ Tools                │    │
│  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘    │
│         │                │                    │                │
│         ▼                ▼                    ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LangChain Tool Wrappers                     │   │
│  │  @tool decorator / BaseTool subclass                    │   │
│  │  - Input/output schema via Pydantic                     │   │
│  │  - Error handling → ToolException                       │   │
│  │  - Async support via arun()                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LangGraph Tool Node                         │   │
│  │  ToolNode(tools=[...]) — handles tool calls from        │   │
│  │  LLM messages and routes results back to state          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Tool Wrapper Examples

```python
# python-agent/tools/sandbox_tool.py
from langchain_core.tools import tool
from pydantic import BaseModel

class SandboxExecuteInput(BaseModel):
    command: str
    working_dir: str
    timeout_seconds: int = 30

@tool("sandbox_execute", args_schema=SandboxExecuteInput)
def sandbox_execute(command: str, working_dir: str, timeout_seconds: int = 30) -> dict:
    """
    Execute a command in the Java Sandbox with security policy enforcement.
    Returns stdout, stderr, and exit code.
    """
    from ..client.sandbox_client import SandboxClient
    client = SandboxClient()
    return client.execute(command, working_dir, timeout_seconds)


# python-agent/tools/validation_tool.py
from langchain_core.tools import tool

@tool("validate_generated_code")
def validate_generated_code(artifact_dir: str) -> dict:
    """
    Run the Validation Gate on a generated code artifact directory.
    Returns validation result with pass/fail status and error details.
    """
    from ..generators.validation_gate import ValidationGate
    gate = ValidationGate()
    return gate.validate(artifact_dir)
```

### 3.4 Plugin Tool Integration

Existing plugins in `python-agent/plugins/` are wrapped as LangChain tools using a dynamic loader:

```python
# python-agent/tools/plugin_tool_loader.py
from langchain_core.tools import StructuredTool
from ..plugins import PluginRegistry

def load_plugin_tools() -> list:
    """
    Dynamically load all registered plugins as LangChain StructuredTools.
    Enables LangGraph nodes to call plugins via the standard tool interface.
    """
    tools = []
    for plugin_name, plugin in PluginRegistry.all().items():
        tool = StructuredTool.from_function(
            func=plugin.execute,
            name=plugin_name,
            description=plugin.description,
            args_schema=plugin.input_schema,
        )
        tools.append(tool)
    return tools
```

---

## 4. Integration Points Between LangGraph Workflows and Existing Components

### 4.1 Integration Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                            │
│                                                                 │
│  [intent_node] ──────────────────────────────────────────────┐ │
│       │ uses: ModelAdapterFactory(INTENT_CLASSIFICATION)      │ │
│       │ reads: task dict from AgentState                      │ │
│       │ writes: intent, confidence to AgentState              │ │
│                                                               │ │
│  [planner_node] ─────────────────────────────────────────────┤ │
│       │ uses: ModelAdapterFactory(PLANNING)                   │ │
│       │ uses: StructuredOutputParser(PlanSchema)              │ │
│       │ writes: plan to AgentState                            │ │
│                                                               │ │
│  [coder_node] ───────────────────────────────────────────────┤ │
│       │ uses: ModelAdapterFactory(CODE_GENERATION)            │ │
│       │ calls: BackendGenerator / WebGenerator (existing)     │ │
│       │ writes: generated_files to AgentState                 │ │
│                                                               │ │
│  [validation_node] ──────────────────────────────────────────┤ │
│       │ calls: ValidationGate.validate() (existing)           │ │
│       │ writes: validation_result to AgentState               │ │
│       │ edge: pass → artifact_node, fail → fix_node           │ │
│                                                               │ │
│  [fix_node] ─────────────────────────────────────────────────┤ │
│       │ uses: ModelAdapterFactory(FIX_LOOP)                   │ │
│       │ calls: FixLoop.attempt_repair() (existing)            │ │
│       │ increments: fix_attempts in AgentState                │ │
│       │ edge: fix_attempts < 3 → validation_node              │ │
│       │       fix_attempts >= 3 → error_node                  │ │
│                                                               │ │
│  [artifact_node] ────────────────────────────────────────────┤ │
│       │ calls: ArtifactService.upload() via HTTP              │ │
│       │ writes: artifact_url to AgentState                    │ │
│                                                               │ │
│  [event_node] ───────────────────────────────────────────────┘ │
│       │ calls: BaseAgent.publish_event() (existing outbox)      │
│       │ publishes: TASK_SUCCEEDED or TASK_FAILED event          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Existing Component Reuse

The following existing components are called directly from LangGraph nodes without modification:

| Existing Component | Called From | Interface |
|---|---|---|
| `BackendGenerator` | `coder_node` | `generator.generate(plan) → files` |
| `FastAPIGenerator` | `coder_node` | `generator.generate(plan) → files` |
| `ValidationGate` | `validation_node` | `gate.validate(dir) → result` |
| `FixLoop` | `fix_node` | `loop.attempt_repair(files, errors) → files` |
| `BaseAgent.publish_event` | `event_node` | `agent.publish(event_type, payload)` |
| `DistributedTaskLock` | Orchestrator | `lock.acquire(task_id)` / `lock.release()` |
| `CircuitBreaker` | ModelAdapterFactory | `cb.call(fn, context)` |
| `ControlPlaneClient` | `event_node` | `client.post_event(event)` |

### 4.3 Structured Output Integration

LangGraph nodes use LangChain's structured output to enforce schema at each agent boundary:

```python
# python-agent/workflows/nodes/planner_node.py
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel
from typing import List

class PlanStep(BaseModel):
    step_id: str
    description: str
    agent: str
    dependencies: List[str]

class PlanSchema(BaseModel):
    plan_name: str
    steps: List[PlanStep]
    risk_level: str   # "low" | "medium" | "high"
    estimated_duration_seconds: int

def planner_node(state: AgentState) -> AgentState:
    model = model_factory.get_model(ModelRole.PLANNING)
    parser = PydanticOutputParser(pydantic_object=PlanSchema)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a planning agent. {format_instructions}"),
        ("human", "Create a plan for: {intent}"),
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | model | parser

    try:
        plan = chain.invoke({"intent": state["intent"]})
        return {**state, "plan": plan.model_dump()}
    except Exception as e:
        # Fallback: use legacy planner if structured output fails
        from ...agents.planner_agent import PlannerAgent
        legacy_plan = PlannerAgent().create_plan(state["intent"])
        return {**state, "plan": legacy_plan, "error_code": "STRUCTURED_OUTPUT_FALLBACK"}
```

---

## 5. Error Handling and Fallback Strategies

### 5.1 Error Taxonomy for LangGraph Operations

**Requirement 8.6:** When LangGraph operations fail, the system SHALL provide clear error categorization and fallback options.

LangGraph-specific errors are mapped to the system's standard error taxonomy:

| LangGraph Error | System Error Code | Retryable | Fallback |
|---|---|---|---|
| LLM API timeout | `LLMError.TIMEOUT` | Yes | Retry with backoff; fall back to legacy engine |
| LLM API rate limit | `LLMError.RATE_LIMIT` | Yes | Retry after delay; circuit breaker |
| Structured output parse failure | `LLMError.PARSE_FAILURE` | Yes (1x) | Use legacy unstructured output |
| Circuit breaker open | `LLMError.CIRCUIT_OPEN` | No | Fall back to legacy engine immediately |
| Node execution exception | `ValidationError.NODE_FAILURE` | Depends | Retry node; fall back to legacy |
| State schema violation | `ProtocolError.STATE_INVALID` | No | Log and fail task |
| Checkpointer failure | `ProtocolError.CHECKPOINT_FAILURE` | Yes | Continue without checkpoint |
| Tool execution failure | `SandboxError` / `PluginError` | Depends | Existing tool error handling |

### 5.2 Node-Level Error Handling

Each LangGraph node wraps its execution in a standardized error handler:

```python
# python-agent/workflows/nodes/base_node.py
from functools import wraps
from ..state import AgentState
from ...utils.errors import LLMError, ProtocolError, classify_error
from ...utils.observability import get_logger

logger = get_logger(__name__)

def node_error_handler(node_name: str):
    """
    Decorator that wraps LangGraph node functions with standardized
    error handling, logging, and fallback logic.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(state: AgentState) -> AgentState:
            try:
                return fn(state)
            except Exception as e:
                error_code, is_retryable = classify_error(e)
                logger.error(
                    "LangGraph node failed",
                    extra={
                        "task_id": state.get("task_id"),
                        "trace_id": state.get("trace_id"),
                        "node": node_name,
                        "error_code": error_code,
                        "retryable": is_retryable,
                        "error": str(e),
                    }
                )
                return {
                    **state,
                    "error_code": error_code,
                    "error_message": str(e),
                }
        return wrapper
    return decorator
```

### 5.3 Workflow-Level Fallback to Legacy Engine

When a LangGraph workflow encounters a non-retryable error, the orchestrator falls back to the legacy engine for the same task:

```python
# python-agent/orchestrator/agent_orchestrator.py

class AgentOrchestrator:
    def _run_langgraph(self, task: dict, intent: str) -> dict:
        try:
            workflow = self._get_workflow(intent)
            result = workflow.invoke(self._build_initial_state(task))

            if result.get("error_code") and not self._is_retryable(result["error_code"]):
                logger.warning(
                    "LangGraph non-retryable failure, falling back to legacy",
                    extra={
                        "task_id": task["task_id"],
                        "error_code": result["error_code"],
                        "intent": intent,
                    }
                )
                return self._run_legacy(task, intent)

            return result

        except Exception as e:
            logger.error(
                "LangGraph workflow exception, falling back to legacy",
                extra={"task_id": task["task_id"], "error": str(e)},
            )
            return self._run_legacy(task, intent)
```

### 5.4 Circuit Breaker Integration

The circuit breaker from `python-agent/utils/circuit_breaker.py` is integrated at the model adapter level. When the circuit opens (3 consecutive LLM failures), all LangGraph nodes using that model role immediately fall back to the legacy engine:

```python
# Circuit breaker state affects engine selection
class AgentOrchestrator:
    def handle_task(self, task: dict) -> dict:
        intent = self._classify_intent(task)

        # If circuit is open for the required model role, use legacy
        required_role = INTENT_TO_MODEL_ROLE[intent]
        if self._circuit_breaker.is_open(required_role.value):
            logger.info(
                "Circuit open for model role, using legacy engine",
                extra={"role": required_role.value, "intent": intent},
            )
            return self._run_legacy(task, intent)

        if AGENT_ENGINE == "langgraph" or intent in LANGGRAPH_INTENTS:
            return self._run_langgraph(task, intent)
        return self._run_legacy(task, intent)
```

### 5.5 Checkpointing and Recovery

LangGraph's built-in checkpointing enables mid-workflow recovery after crashes:

```python
# python-agent/workflows/workflow_factory.py
from langgraph.checkpoint.redis import RedisSaver
import redis

def create_workflow_with_checkpointing(graph_builder, task_id: str):
    """
    Creates a LangGraph workflow with Redis-backed checkpointing.
    Enables recovery from the last successful node after a crash.
    """
    redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"))
    checkpointer = RedisSaver(redis_client)

    graph = graph_builder.compile(checkpointer=checkpointer)

    # Thread ID scoped to task for isolation
    config = {"configurable": {"thread_id": task_id}}
    return graph, config
```

If the Python Agent crashes mid-workflow, the next execution resumes from the last checkpoint rather than restarting from the beginning. This complements the existing event outbox recovery mechanism.

---

## 6. Observability Integration

### 6.1 LangGraph-Specific Metrics

The following Prometheus metrics are added for LangGraph operations:

```
# Node execution duration
langgraph_node_duration_seconds{workflow, node, status}

# Fallback events
langgraph_fallback_to_legacy_total{intent, reason}

# Structured output parse failures
langgraph_parse_failure_total{node, model_role}

# Checkpoint operations
langgraph_checkpoint_write_total{workflow, status}
langgraph_checkpoint_read_total{workflow, status}
```

### 6.2 Trace Propagation

The `trace_id` from `AgentState` is propagated through all LangChain calls via LangSmith callbacks (when enabled) and through structured log fields:

```python
# python-agent/workflows/nodes/base_node.py
from langchain_core.callbacks import BaseCallbackHandler

class TraceCallbackHandler(BaseCallbackHandler):
    def __init__(self, trace_id: str, task_id: str):
        self.trace_id = trace_id
        self.task_id = task_id

    def on_llm_start(self, serialized, prompts, **kwargs):
        logger.debug(
            "LLM call started",
            extra={
                "trace_id": self.trace_id,
                "task_id": self.task_id,
                "model": serialized.get("name"),
            }
        )
```

---

## 7. Dependency Requirements

The following packages are added to `python-agent/requirements.txt`:

```
# LangChain core
langchain-core==0.2.38
langchain-openai==0.1.23
langchain-anthropic==0.1.23

# LangGraph
langgraph==0.2.28
langgraph-checkpoint-redis==0.1.0

# Structured output
pydantic==2.8.2
```

All versions are pinned. Upgrades follow the project's weekly upgrade window with automated regression testing.

---

## 8. Testing Strategy

### 8.1 Unit Tests

Each adapter and node is unit-tested in isolation:

- `ModelAdapterFactory`: verify correct model class instantiated per role and provider
- `node_error_handler`: verify error codes are correctly classified and logged
- Tool wrappers: verify input/output schema validation and error propagation

### 8.2 Integration Tests

- Full workflow execution with mocked LLM responses (deterministic outputs)
- Fallback path: verify legacy engine is invoked when circuit is open
- Checkpointing: verify workflow resumes from correct node after simulated crash

### 8.3 Dual-Engine Comparison Tests

See `langgraph-migration-roadmap.md` Section 5 for the comparison testing framework that validates output parity between LangChain/LangGraph and legacy engines.

---

## 9. References

- Requirements: 8.5 (LangChain integration), 8.6 (error handling and fallback)
- Design: Properties 28 (LangGraph integration compatibility), 29 (LangGraph error handling)
- Related docs:
  - `langgraph-migration-roadmap.md` — migration phases and dual-engine comparison
  - `langchain-langgraph-agent-upgrade-plan-2026-04.md` — original upgrade strategy
  - `python-agent/utils/circuit_breaker.py` — circuit breaker implementation
  - `python-agent/utils/errors.py` — error taxonomy
