# LangGraph Migration Roadmap

**Version:** 1.0  
**Date:** 2026-05  
**Scope:** Python Agent Orchestration → LangGraph State Machine  
**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

---

## 1. Overview

This document defines the migration roadmap for evolving the Python Agent's orchestration layer from the current legacy DAG-based system to a LangGraph state machine. The migration follows a phased, dual-engine approach: the legacy engine remains fully operational throughout, and LangGraph is introduced incrementally per operation type with comparison testing at each stage.

The guiding principle is **zero regression tolerance**: every LangGraph workflow must demonstrate output parity with the legacy engine before traffic is shifted.

---

## 2. Current Legacy Orchestration Capabilities

### 2.1 Architecture

The current Python Agent uses a custom DAG scheduler (`python-agent/orchestrator/dag_scheduler.py`) to coordinate five agents in a directed acyclic graph:

```
Intent Agent → Planner Agent → Coder Agent → Reviewer Agent
                                           ↘ Tester Agent
                                           → Merge/Artifact
```

**Key characteristics:**
- Sequential execution with optional parallel branches (Reviewer ‖ Tester)
- State passed as Python dicts between agent calls
- Error handling via try/except with manual retry logic
- No built-in checkpointing or resumability
- Engine selection not configurable at runtime

### 2.2 Supported Operations

| Operation | Agent Chain | Current Status |
|---|---|---|
| `analyze` | Intent → Planner | Stable |
| `test` | Intent → Planner → Tester | Stable |
| `code_change` | Intent → Planner → Coder → Reviewer → Tester | Stable |
| `backend_generation` | Intent → Planner → Coder (BackendGenerator) → Validation → FixLoop | Stable |
| `deploy` | Intent → Planner → Coder → Approval → Deploy | Stable |

### 2.3 Known Limitations

1. No mid-execution checkpointing — a crash restarts the entire chain
2. Parallel branches (Reviewer ‖ Tester) require manual synchronization
3. Error categorization is coarse — all failures surface as generic exceptions
4. No structured output schema enforcement between agents
5. Engine behavior cannot be changed without code deployment

---

## 3. LangGraph Target State

### 3.1 Architecture

The LangGraph engine replaces the custom DAG scheduler with a typed state machine. Each agent becomes a LangGraph node; edges encode conditional transitions and parallel fan-out/fan-in.

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph State Machine                       │
│                                                                 │
│  START → [intent_node] → [planner_node] → [router_node]        │
│                                                ↓                │
│                              ┌─────────────────────────────┐   │
│                              │  code_change / backend_gen  │   │
│                              │  [coder_node]               │   │
│                              │       ↓                     │   │
│                              │  [reviewer_node] ──────┐    │   │
│                              │  [tester_node]  ───────┤    │   │
│                              │       ↓ (merge)        │    │   │
│                              │  [artifact_node]       │    │   │
│                              └─────────────────────────────┘   │
│                                                ↓                │
│                                              END                │
└─────────────────────────────────────────────────────────────────┘
```

**Key improvements over legacy:**
- Typed `AgentState` TypedDict enforces schema between nodes
- Built-in checkpointing via LangGraph `MemorySaver` / Redis checkpointer
- Native parallel fan-out with `Send` API for Reviewer ‖ Tester
- Conditional edges replace manual if/else routing
- Structured output validation at each node boundary
- Engine selectable via `AGENT_ENGINE=legacy|langgraph` environment variable

### 3.2 State Schema

```python
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    task_id: str
    run_id: str
    trace_id: str
    intent: str                    # classified operation type
    confidence: float
    plan: Optional[dict]           # structured plan from Planner
    generated_files: List[str]     # paths to generated artifacts
    validation_result: Optional[dict]
    fix_attempts: int
    error_code: Optional[str]
    error_message: Optional[str]
    artifact_url: Optional[str]
    engine: str                    # "legacy" | "langgraph"
```

### 3.3 Engine Router

The `Orchestrator` class gains a top-level engine router that dispatches to either engine based on configuration:

```python
# python-agent/orchestrator/agent_orchestrator.py
import os

AGENT_ENGINE = os.getenv("AGENT_ENGINE", "legacy")
LANGGRAPH_INTENTS = set(os.getenv("LANGGRAPH_INTENTS", "").split(","))

class AgentOrchestrator:
    def handle_task(self, task: dict) -> dict:
        intent = self._classify_intent(task)
        if AGENT_ENGINE == "langgraph" or intent in LANGGRAPH_INTENTS:
            return self._run_langgraph(task, intent)
        return self._run_legacy(task, intent)
```

This satisfies **Requirement 8.1**: both engines are selectable via configuration flag without code changes.

---

## 4. Migration Phases

### Phase 1: Analyze and Test Operations (Low Risk)

**Target operations:** `analyze`, `test`  
**Validates: Requirement 8.2**

These operations have the simplest agent chains (Intent → Planner, Intent → Planner → Tester) and produce deterministic, easily comparable outputs. They are the safest entry point for LangGraph.

**Steps:**
1. Implement `python-agent/workflows/analyze_workflow.py` as a LangGraph graph
2. Implement `python-agent/workflows/test_workflow.py` as a LangGraph graph
3. Enable via `LANGGRAPH_INTENTS=analyze,test` (legacy handles all other operations)
4. Run dual-engine comparison tests for 1 week at 10% traffic
5. Promote to 100% after comparison tests pass

**Acceptance criteria:**
- Output structure matches legacy for ≥ 99% of test cases
- P95 latency does not increase by more than 15%
- Zero regressions in existing test suite

**Rollback:** Set `LANGGRAPH_INTENTS=` (empty) — all traffic returns to legacy immediately.

---

### Phase 2: Code Change Operations (Medium Risk)

**Target operations:** `code_change`  
**Validates: Requirement 8.3**

The `code_change` chain includes parallel Reviewer ‖ Tester branches, which benefit most from LangGraph's native parallel execution.

**Steps:**
1. Implement `python-agent/workflows/code_change_workflow.py`
2. Use LangGraph `Send` API for parallel Reviewer and Tester nodes
3. Enable via `LANGGRAPH_INTENTS=analyze,test,code_change`
4. Run dual-engine comparison tests for 2 weeks at 20% traffic
5. Promote to 100% after comparison tests pass

**Acceptance criteria:**
- Output consistency ≥ 99% vs legacy (Requirement 8.4)
- Parallel execution reduces P95 latency by ≥ 10% vs sequential legacy
- Fix loop integration works correctly within LangGraph state

**Rollback:** Remove `code_change` from `LANGGRAPH_INTENTS`.

---

### Phase 3: Backend Generation Operations (High Complexity)

**Target operations:** `backend_generation`  
**Validates: Requirement 8.3**

Backend generation involves the validation gate and fix loop, which require iterative state transitions — a natural fit for LangGraph's conditional edges.

**Steps:**
1. Implement `python-agent/workflows/backend_generation_workflow.py`
2. Model the fix loop as a conditional edge: `validation_node → fix_node → validation_node` (max 3 iterations)
3. Enable via `LANGGRAPH_INTENTS=analyze,test,code_change,backend_generation`
4. Run dual-engine comparison tests for 2 weeks at 10% traffic
5. Promote to 100% after comparison tests pass

**Acceptance criteria:**
- Backend generation success rate ≥ 90% (Requirement 3.7)
- Fix loop iteration count matches or improves vs legacy
- Artifact packaging and upload works correctly

**Rollback:** Remove `backend_generation` from `LANGGRAPH_INTENTS`.

---

### Phase 4: Deploy Operations (Highest Risk)

**Target operations:** `deploy`  
**Validates: Requirement 8.3**

Deploy operations include the human-in-the-loop (HITL) approval node, which is a unique LangGraph capability with no direct legacy equivalent.

**Steps:**
1. Implement `python-agent/workflows/deploy_workflow.py`
2. Use LangGraph `interrupt` for the approval gate (HITL)
3. Enable via `AGENT_ENGINE=langgraph` (full migration)
4. Run dual-engine comparison tests for 4 weeks at 5% traffic
5. Promote to 100% after extended validation

**Acceptance criteria:**
- Approval gate correctly pauses and resumes execution
- Deploy success rate matches legacy
- Audit trail is complete for all approval decisions

**Rollback:** Set `AGENT_ENGINE=legacy`.

---

### Phase 5: Legacy Deprecation

After all operations have been running on LangGraph at 100% traffic for a minimum of 4 weeks with no regressions:

1. Archive legacy DAG scheduler code (do not delete — keep for reference)
2. Remove `AGENT_ENGINE=legacy` code path
3. Remove dual-engine comparison test infrastructure
4. Update documentation to reflect LangGraph as the sole engine

---

## 5. Dual-Engine Comparison Testing Framework

### 5.1 Purpose

The comparison framework validates **Requirement 8.4**: output consistency between legacy and LangGraph engines during migration. It runs both engines on the same input and compares outputs, flagging divergences for investigation.

### 5.2 Framework Design

```python
# python-agent/testing/dual_engine_comparator.py

import asyncio
from dataclasses import dataclass
from typing import Any

@dataclass
class ComparisonResult:
    task_id: str
    intent: str
    legacy_output: dict
    langgraph_output: dict
    consistent: bool
    divergence_fields: list[str]
    legacy_duration_ms: float
    langgraph_duration_ms: float

class DualEngineComparator:
    """
    Runs the same task through both engines and compares outputs.
    Used during migration phases to validate LangGraph parity.
    """

    def __init__(self, legacy_engine, langgraph_engine):
        self.legacy = legacy_engine
        self.langgraph = langgraph_engine

    async def compare(self, task: dict) -> ComparisonResult:
        legacy_result, langgraph_result = await asyncio.gather(
            self._run_timed(self.legacy, task),
            self._run_timed(self.langgraph, task),
        )
        divergences = self._find_divergences(
            legacy_result["output"], langgraph_result["output"]
        )
        return ComparisonResult(
            task_id=task["task_id"],
            intent=task.get("intent", "unknown"),
            legacy_output=legacy_result["output"],
            langgraph_output=langgraph_result["output"],
            consistent=len(divergences) == 0,
            divergence_fields=divergences,
            legacy_duration_ms=legacy_result["duration_ms"],
            langgraph_duration_ms=langgraph_result["duration_ms"],
        )

    def _find_divergences(self, legacy: dict, langgraph: dict) -> list[str]:
        """Return list of top-level keys where outputs differ."""
        divergences = []
        all_keys = set(legacy.keys()) | set(langgraph.keys())
        for key in all_keys:
            if legacy.get(key) != langgraph.get(key):
                divergences.append(key)
        return divergences
```

### 5.3 Comparison Metrics

The framework emits the following Prometheus metrics:

```
# Consistency rate per intent type
langgraph_comparison_consistent_total{intent="analyze"}
langgraph_comparison_divergent_total{intent="analyze"}

# Latency comparison
langgraph_duration_ms{engine="legacy", intent="analyze"}
langgraph_duration_ms{engine="langgraph", intent="analyze"}

# Success rate comparison
langgraph_success_total{engine="legacy", intent="analyze"}
langgraph_success_total{engine="langgraph", intent="analyze"}
```

### 5.4 Promotion Criteria

A LangGraph workflow is eligible for promotion to 100% traffic when:

| Metric | Threshold |
|---|---|
| Output consistency rate | ≥ 99% over 7-day window |
| LangGraph success rate | ≥ legacy success rate |
| P95 latency ratio (LangGraph / legacy) | ≤ 1.15 |
| Zero critical divergences | (divergences in `artifact_url`, `error_code`) |

### 5.5 Automatic Rollback Triggers

| Condition | Action |
|---|---|
| Consistency rate drops below 95% | Remove intent from `LANGGRAPH_INTENTS` |
| LangGraph success rate drops 2% below legacy | Remove intent from `LANGGRAPH_INTENTS` |
| P95 latency increases > 20% | Remove intent from `LANGGRAPH_INTENTS` |

---

## 6. Rollback Strategy

### 6.1 Granular Rollback (Per Intent)

```bash
# Remove a specific intent from LangGraph routing
export LANGGRAPH_INTENTS="analyze,test"   # removes code_change
# Restart Python Agent — takes effect immediately
```

### 6.2 Full Engine Rollback

```bash
# Revert all traffic to legacy engine
export AGENT_ENGINE=legacy
# Restart Python Agent
```

### 6.3 Rollback Red Lines

Immediate full rollback is triggered if any of the following occur:

- Task success rate drops > 1% vs baseline
- P95 latency increases > 20% vs baseline
- Duplicate task execution rate exceeds 0.1%
- Event loss rate exceeds 0.01%
- Any data corruption in generated artifacts

---

## 7. Migration Timeline

| Phase | Operations | Duration | Traffic Ramp |
|---|---|---|---|
| Phase 1 | analyze, test | 2 weeks | 10% → 100% |
| Phase 2 | code_change | 3 weeks | 20% → 100% |
| Phase 3 | backend_generation | 3 weeks | 10% → 100% |
| Phase 4 | deploy | 6 weeks | 5% → 100% |
| Phase 5 | Legacy deprecation | 2 weeks | — |

Total estimated duration: ~16 weeks from Phase 1 start.

---

## 8. Success Criteria

The migration is complete when:

1. All five operation types run exclusively on LangGraph at 100% traffic
2. Task success rate meets or exceeds pre-migration baseline (Requirement 8.7)
3. P95 latency meets or improves vs pre-migration baseline (Requirement 8.7)
4. Dual-engine comparison tests show ≥ 99% consistency across all operation types
5. Zero regressions in the existing test suite
6. Legacy DAG scheduler archived and documented

---

## 9. References

- Requirements: 8.1 (dual engine), 8.2 (analyze/test via LangGraph), 8.3 (code_change/backend_gen/deploy migration), 8.4 (output consistency), 8.5 (LangChain integration), 8.6 (error handling), 8.7 (performance parity)
- Design: Properties 25–29 (dual engine, LangGraph operations, consistency, integration, error handling)
- Related docs:
  - `langchain-integration-architecture.md` — LangChain adapter layer design
  - `langchain-langgraph-agent-upgrade-plan-2026-04.md` — original upgrade strategy
  - `backend-upgrade-master-plan-2026-04.md` — overall upgrade context
