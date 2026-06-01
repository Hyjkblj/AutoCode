# Super Individual — Architecture Document

> AI-driven end-to-end fullstack delivery system, built on AutoCode's multi-agent pipeline.

## Overview

The "Super Individual" extends AutoCode's existing 5-agent pipeline (Intent → Planner → Coder → Reviewer → Tester) with 7 new capabilities:

1. **GitTool** — Git operations (clone, checkout, commit, push)
2. **CodeIndex** — Lightweight TS/JS code understanding via regex parsing
3. **RepoBootstrap** — Repository cloning + dependency installation
4. **DialogueManager** — LLM-driven requirement clarification
5. **TestGenerator** — Automatic test generation from source code
6. **KnowledgeExtractor** — Cross-task knowledge persistence
7. **HumanGate** — Pipeline stage approval gating

## Pipeline Flow

```
User Request
    │
    ▼
[RepoBootstrap] ── clone repo, install deps
    │
    ▼
[CodeIndex] ── scan repo, build symbol index
    │
    ▼
[DialogueManager] ── clarify requirements if vague
    │
    ▼
[IntentAgent] ── classify intent (code_change / analyze / deploy)
    │
    ▼
[PlannerAgent] ── generate execution plan
    │
    ▼
[HumanGate: PLAN] ── optional approval gate
    │
    ▼
[CoderAgent] ── incremental code edits using CodeIndex
    │
    ▼
[HumanGate: CODE] ── optional approval gate
    │
    ▼
[ValidationGate] ── TS/React/Express validation
    │
    ▼
[ReviewerAgent] + [TesterAgent] ── parallel review + test
    │                                   │
    ▼                                   ▼
[TestGenerator] ── auto-generate tests
    │
    ▼
[KnowledgeExtractor] ── extract and store knowledge
    │
    ▼
[TASK_DONE]
```

## New Components

### GitTool (`python-agent/tools/git_tool.py`)
Wraps git CLI for repository operations. Supports local subprocess mode and sandbox ExecTool mode.

### CodeIndex (`python-agent/tools/code_index.py`)
Regex-based TS/JS parser that extracts: functions, classes, interfaces, types, constants, reducers. Tracks import/export relationships for dependency analysis.

### RepoBootstrap (`python-agent/tools/repo_bootstrap.py`)
Orchestrates git clone + npm install. Returns BootstrapResult with file count and dependency status.

### DialogueManager (`python-agent/agents/dialogue_manager.py`)
Uses LLM to detect vague prompts and generate clarification questions. Maintains conversation turn history.

### TestGenerator (`python-agent/generators/test_generator.py`)
Detects test framework from package.json (jest/vitest/mocha) and generates tests via LLM.

### KnowledgeExtractor (`python-agent/memory/knowledge_extractor.py`)
Extracts file summaries and project architecture via LLM. Stores in Redis for cross-task persistence.

### HumanGate (`python-agent/plugins/human_gate.py`)
Configurable pipeline stage gating. Supports plan/code/test/deploy stages. Integrates with existing APPROVAL_REQUIRED event protocol.

## Event Protocol

8 new event types added to the shared protocol:

| Event | Direction | Purpose |
|-------|-----------|---------|
| CLARIFICATION_REQUESTED | Agent → UI | Ask user for clarification |
| CLARIFICATION_ANSWERED | UI → Agent | User's clarification response |
| REPO_BOOTSTRAP_STARTED | Agent → UI | Clone started |
| REPO_BOOTSTRAP_DONE | Agent → UI | Workspace ready |
| CODE_INDEX_BUILT | Agent → UI | Index completed |
| PLAN_APPROVAL_REQUESTED | Agent → UI | Plan awaiting approval |
| TEST_GENERATED | Agent → UI | Tests auto-generated |
| KNOWLEDGE_WRITEBACK | Agent → UI | Knowledge stored |

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| MVP_USE_LOCAL_GIT | false | Use local git instead of sandbox |
| MVP_APPROVAL_STAGES | (none) | Comma-separated stages to gate |
| MVP_ALLOWED_WORKSPACE_PREFIXES | (none) | Allowed workspace paths |
