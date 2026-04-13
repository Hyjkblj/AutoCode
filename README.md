# AutoCode Backend MVP

Runnable multi-agent backend platform with:

- Spring control plane (`control-plane-spring`)
- Java execution/sandbox agent (`pc-agent-java`)
- Python AI orchestration agent (`python-agent`)
- Shared cross-language contracts (`shared-protocol`)

## Modules

- `control-plane-spring`
  - REST + STOMP/WebSocket control plane
  - task lifecycle/state machine
  - approvals, audit chain, artifacts, RBAC
  - MySQL persistence + Redis queue support
- `pc-agent-java`
  - node runtime for command execution
  - policy-based security gate + approval wait
  - localhost sandbox HTTP API (`/sandbox/*`)
  - artifact/runtime metadata reporting
- `python-agent`
  - AI workflow orchestration (`Intent -> Planner -> Coder -> Reviewer/Tester`)
  - DAG parallel stage scheduling
  - Redis-backed memory with in-memory fallback
  - calls Java sandbox for command/test/deploy execution
- `shared-protocol`
  - shared DTOs (`TaskEvent`, `SandboxExecuteRequest/Response`, `ArtifactMetadata`, ...)
  - JSON-schema-aligned validators for events/sandbox/manifests/runtime descriptors

## End-to-End Flow

1. Operator creates a task (`POST /api/v1/tasks`).
2. Control plane persists `QUEUED` task, emits `TASK_CREATED`, enqueues it.
3. Agent polls (`GET /api/v1/agent/tasks/next`) and claims task atomically.
4. Agent executes and streams events (`ASSISTANT_OUTPUT`, `TOOL_*`, `APPROVAL_*`, `FILE_PATCH_PREVIEW`, `ARTIFACT_READY`, ...).
5. Control plane ingests events, folds state transitions, persists event log, writes audit records.
6. WebSocket broadcasts updates via `/topic/tasks/{taskId}`.
7. Task ends with `TASK_DONE` or `TASK_FAILED`.

## Security Model

- Control plane auth modes:
  - `token` mode (legacy token filter)
  - `jwt` mode (resource server + roles mapping)
- JWT mode still supports legacy `X-Agent-Token` adapter for agent compatibility.
- Project-level authorization is enforced via method security (`@projectAuthz`).
- Task/artifact security uses non-enumeration behavior (`404` on unauthorized task-scoped access).
- Optional mTLS enforcement is scoped to `/api/v1/agent/**` (not global operator endpoints).
- Java agent command execution is guarded by a policy chain:
  - privilege escalation detection (`sudo`, `runas`, ...)
  - sensitive env var access detection
  - network access gating
  - file read/write path restrictions
  - workspace allowlist enforcement
- Sandbox server is localhost-only (`127.0.0.1`) and validates request/response contracts.
- Approval context binding is enforced for high-risk actions (including deploy context checks).

## Python Agent Design

- `AgentRunner`: register, heartbeat, poll loop.
- `AgentOrchestrator`:
  - intent classification (`IntentAgent`)
  - plan generation (`PlannerAgent`)
  - code generation/patch emission (`CoderAgent`)
  - parallel review + test via `DagScheduler`
  - optional web artifact packaging/upload (`export.zip`)
- `ExecTool` delegates command execution to Java sandbox (`/sandbox/execute`).
- `RedisMemory` reuses prior test/deploy command context per project/session/workspace key.

## Protocol Contracts

`shared-protocol` defines and validates event and sandbox contracts, including:

- `TaskEvent` + `EventType`
- `SandboxExecuteRequest` / `SandboxExecuteResponse`
- `ToolManifest` and permissions envelope
- `ArtifactMetadata` / `ArtifactManifest`
- `ServiceRuntimeDescriptor`

This keeps Java and Python components consistent while evolving independently.

## Run With Docker (Recommended)

Start full stack (MySQL, Redis, control-plane, Java agent, Python agent):

```bash
docker compose --profile fullstack up -d --build
```

Control plane endpoint:

```text
http://localhost:8058
```

Stop:

```bash
docker compose --profile fullstack down
```

Notes:

- `python-agent` shares the Java agent network namespace so sandbox calls use `127.0.0.1:18080`.
- Optional hosted artifact link settings:
  - `MVP_ARTIFACTS_HOSTING_PUBLIC_BASE_URL`
  - `MVP_ARTIFACTS_DOWNLOAD_SHARED_TOKEN`

## Local Dev Quick Start

0. Ensure JDK 17+ (JDK 21 recommended).
   PowerShell example:
   `$env:JAVA_HOME='D:\Develop\Java\jdk21'; $env:Path="$env:JAVA_HOME\bin;$env:Path"`
1. Start infra:
   `docker compose up -d`
2. Build Java modules:
   `mvn -DskipTests install`
3. Start control plane:
   `cd control-plane-spring && mvn spring-boot:run`
4. Start Java agent:
   `cd pc-agent-java && mvn exec:java -Dexec.mainClass=com.autocode.agent.AgentApplication`
5. (Optional) Start Python agent:
   `cd python-agent && pip install -r requirements.txt && python main.py`
6. Run smoke test:
   `./scripts/smoke-test.ps1`

## Key Environment Variables

- Control plane:
  - `MVP_DB_URL`, `MVP_DB_USERNAME`, `MVP_DB_PASSWORD`
  - `MVP_REDIS_HOST`, `MVP_REDIS_PORT`, `MVP_REDIS_PASSWORD`
  - `MVP_AUTH_MODE` (`jwt` or `token`)
  - `MVP_JWT_SECRET`
  - `MVP_MTLS_REQUIRED_FOR_AGENT`
- Java agent:
  - `MVP_BASE_URL`, `MVP_NODE_ID`, `MVP_AGENT_TOKEN`, `MVP_AGENT_PROFILE`
  - `MVP_ALLOWED_COMMAND_PREFIXES`, `MVP_ALLOWED_WORKSPACE_PREFIXES`
  - `MVP_NETWORK_ALLOWED`
  - `MVP_SANDBOX_SERVER_ENABLED`, `MVP_SANDBOX_PORT`
- Python agent:
  - `MVP_BASE_URL`, `MVP_NODE_ID`, `MVP_AGENT_TOKEN`, `MVP_AGENT_PROFILE`
  - `MVP_SANDBOX_BASE_URL`
  - `MVP_MEMORY_BACKEND`, `MVP_REDIS_URL`
  - `LLM_CONFIG_PATH` (default: `python-agent/configs/doubao-seed-2.0-code-high-perf.json`)
  - `ARK_API_KEY` (recommended for Volcengine Ark profile)
  - optional overrides: `LLM_BACKEND`, `LLM_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

## Detailed Architecture Doc

See full backend architecture and algorithm design here:

- `docs/backend-architecture-java-security-python-agent.md`
