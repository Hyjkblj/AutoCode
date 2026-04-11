# MobileVoice-CodeOps MVP

This repository now contains a runnable MVP implementation based on the architecture docs.

## Modules
- `shared-protocol`: shared task/event models used by control plane and node agent.
- `control-plane-spring`: Spring Boot control plane (REST + STOMP websocket + MySQL persistence + Redis queue).
- `pc-agent-java`: Java node agent (register/heartbeat/poll tasks/publish events).

## What MVP currently supports
1. Create tasks with idempotency key.
2. Agent polling and task execution simulation.
3. Structured event ingestion and websocket broadcast (`/topic/tasks/{taskId}`).
4. Approval flow for high-risk prompts.
5. Task cancel and event history query.
6. MySQL persistence via JPA + Flyway schema migration.
7. Redis-backed task queue with in-memory fallback for local resilience.

## Quick start
0. Ensure JDK 17+ is active (JDK 21 recommended). Example on Windows PowerShell:
   `$env:JAVA_HOME='D:\Develop\Java\jdk21'; $env:Path="$env:JAVA_HOME\bin;$env:Path"`
   Verify with `mvn -v` (it should show Java 17+).
1. Start MySQL and Redis:
   `docker compose up -d`
2. Build all modules:
   `mvn -DskipTests install`
3. Start control plane (in `control-plane-spring` directory):
   `mvn spring-boot:run`
4. Start agent (in `pc-agent-java` directory, new terminal):
   `mvn exec:java -Dexec.mainClass=com.autocode.agent.AgentApplication`
5. Run smoke test:
   `./scripts/smoke-test.ps1`

## Auth defaults
- Operator token: `operator-dev-token`
- Agent token: `agent-dev-token`

## Key environment variables
- Control plane:
  - `MVP_DB_URL`, `MVP_DB_USERNAME`, `MVP_DB_PASSWORD`
  - `MVP_REDIS_HOST`, `MVP_REDIS_PORT`
  - `mvp.auth.operator-token`, `mvp.auth.agent-token` (in `application.yml`)
- Agent:
- `MVP_BASE_URL` (default `http://localhost:8058`), `MVP_NODE_ID`, `MVP_AGENT_TOKEN`
  - `MVP_APPROVAL_TIMEOUT_SECONDS`
  - `MVP_ALLOWED_COMMAND_PREFIXES`

## Architecture practice
- Business orchestration is kept in services (`TaskService`, `AgentRegistryService`).
- Persistence and queueing details are isolated in adapters (`persistence.*`, `service.queue.*`).
- API contracts remain stable while storage implementations can evolve independently.

## Local DB default
- MySQL local default credential is `root / 000000`.
- You can still override it with `MVP_DB_PASSWORD`.
