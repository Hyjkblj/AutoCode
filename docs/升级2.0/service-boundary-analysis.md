# Service Boundary Analysis: Java Microservices Decomposition

**Version:** 1.0  
**Date:** 2026-05  
**Scope:** Control Plane Spring → Target Microservices Architecture  
**Validates: Requirements 11.1**

---

## 1. Overview

This document analyzes the current `control-plane-spring` monolith and defines the target microservices decomposition. The goal is to identify clear service boundaries, data ownership, and interface contracts that enable a safe, incremental extraction of independent services.

The decomposition follows the migration order specified in Requirement 11.2:

> **Gateway → Event Services → Task Services → Artifact Services**

---

## 2. Current Control Plane Module Boundaries

### 2.1 Package Structure

```
com.autocode.controlplane
├── api/                        # HTTP controllers and request/response DTOs
│   ├── TaskController           # Task CRUD, polling, lease management
│   ├── ArtifactsController      # Artifact retrieval and hosting
│   ├── ArtifactShortLinkController
│   ├── AuditController          # Audit log queries
│   ├── AuthController           # Authentication endpoints
│   ├── AgentController          # Agent registration, heartbeat, events
│   ├── ProjectController        # Project management
│   └── GlobalExceptionHandler
│
├── service/                    # Business logic layer
│   ├── TaskService              # Task lifecycle, lease, idempotency
│   ├── ArtifactQueryService     # Artifact lookup and metadata
│   ├── AgentRegistryService     # Agent node registration and tracking
│   ├── audit/AuditService       # Compliance trail generation
│   ├── observability/           # Metrics and tracing
│   ├── protocol/                # Event protocol handling
│   ├── queue/                   # Task queue management
│   ├── mapper/                  # Entity-DTO mapping
│   └── ws/                      # WebSocket session management
│
├── artifacts/                  # Artifact domain (hexagonal architecture)
│   ├── domain/                  # Artifact domain model
│   ├── application/             # Artifact use cases
│   ├── ports/                   # Inbound/outbound ports
│   └── adapters/                # Storage and HTTP adapters
│
├── persistence/                # Data access layer
│   ├── entity/
│   │   ├── TaskEntity           # Task state machine data
│   │   ├── TaskEventEntity      # Event log per task
│   │   ├── ArtifactEntity       # Generated artifact metadata
│   │   ├── ApprovalEntity       # Approval workflow state
│   │   ├── AuditLogEntity       # Immutable audit trail
│   │   ├── AgentNodeEntity      # Registered agent instances
│   │   ├── IdempotencyRecordEntity  # Deduplication keys
│   │   ├── ProjectEntity        # Project grouping
│   │   ├── ProjectMembershipEntity
│   │   ├── UserEntity
│   │   └── UserRoleEntity
│   └── repo/                    # Spring Data JPA repositories
│
├── security/                   # Authentication and authorization
│   ├── JwtSecurityConfig        # JWT resource server setup
│   ├── AgentMtlsEnforcementFilter  # mTLS for agent-to-control-plane
│   ├── ProjectAuthz             # Project-level authorization
│   └── RolesClaimAuthoritiesConverter
│
├── health/                     # Health check endpoints
├── config/                     # Application configuration beans
└── model/                      # Shared domain models (AgentNode)

com.autocode.event
├── EventController              # Event ingestion endpoint
├── EventDeduplicationService    # Redis-based duplicate detection
└── EventAckResponse             # ACK response DTO
```

### 2.2 Current Dependencies Between Modules

```
┌─────────────────────────────────────────────────────────────┐
│                    control-plane-spring                      │
│                                                             │
│  api/ ──────────────────────────────────────────────────┐  │
│    │                                                     │  │
│    ├──► TaskService ──────────────────────────────────┐  │  │
│    │       │                                          │  │  │
│    │       ├──► persistence/repo/TaskRepo             │  │  │
│    │       ├──► persistence/repo/IdempotencyRepo      │  │  │
│    │       ├──► Redis (distributed lock / lease)      │  │  │
│    │       └──► AuditService                          │  │  │
│    │                                                  │  │  │
│    ├──► ArtifactQueryService ─────────────────────────┤  │  │
│    │       │                                          │  │  │
│    │       └──► artifacts/ (hexagonal domain)         │  │  │
│    │               └──► persistence/repo/ArtifactRepo │  │  │
│    │                                                  │  │  │
│    ├──► AgentRegistryService ─────────────────────────┤  │  │
│    │       └──► persistence/repo/AgentNodeRepo        │  │  │
│    │                                                  │  │  │
│    └──► AuditService ─────────────────────────────────┘  │  │
│            └──► persistence/repo/AuditLogRepo             │  │
│                                                           │  │
│  event/ ──────────────────────────────────────────────────┘  │
│    ├──► EventDeduplicationService ──► Redis                  │
│    └──► TaskService (event → task state transition)          │
│                                                             │
│  security/ ─────────────────────────────────────────────────│
│    └──► All controllers (cross-cutting concern)             │
│                                                             │
│  Shared Infrastructure: MySQL, Redis, RabbitMQ              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Coupling Hotspots

| Coupling Point | Description | Decomposition Risk |
|---|---|---|
| `TaskService` ↔ `AuditService` | Every task mutation writes an audit log | Medium — can be decoupled via events |
| `EventController` ↔ `TaskService` | Event ingestion directly transitions task state | High — tight synchronous coupling |
| `ArtifactQueryService` ↔ `TaskEntity` | Artifact lookup joins task metadata | Medium — can be resolved via task ID reference |
| `security/` ↔ all controllers | JWT/mTLS validation is cross-cutting | Low — extract as shared library or gateway filter |
| `IdempotencyRecordEntity` ↔ multiple services | Shared deduplication table | Medium — each service needs its own idempotency store |

---

## 3. Target Microservices

### 3.1 Service Inventory

| Service | Responsibility | Primary Data | Port (target) |
|---|---|---|---|
| **Task Service** | Task lifecycle, lease management, idempotency | `tasks`, `idempotency_records` | 8061 |
| **Event Service** | Event ingestion, ACK, deduplication, sequence | `task_events`, `event_dedup_keys` | 8062 |
| **Artifact Service** | Artifact storage, packaging, hosting, retention | `artifacts` | 8063 |
| **Approval Service** | Approval workflow, security gates, RBAC | `approvals`, `users`, `user_roles`, `project_memberships` | 8064 |
| **Audit Service** | Immutable compliance trail, audit queries | `audit_logs` | 8065 |

The existing `control-plane-spring` monolith continues to run during migration and is gradually hollowed out as services are extracted.

### 3.2 Task Service

**Responsibility:** Owns the task state machine. Handles task creation, polling, lease acquisition, lease renewal, and terminal state transitions (SUCCEEDED, FAILED, CANCELED).

**Data Ownership:**
- `tasks` table (sole writer)
- `idempotency_records` table (sole writer)
- Redis keys: `task:lock:{taskId}`, `task:lease:{taskId}`

**Inbound API:**
```
POST   /tasks                    # Create task (idempotency key required)
GET    /tasks/{taskId}           # Get task status
POST   /tasks/poll               # Agent polls for next available task
POST   /tasks/{taskId}/lease     # Acquire/renew lease
DELETE /tasks/{taskId}/lease     # Release lease
POST   /tasks/{taskId}/complete  # Mark task terminal
```

**Outbound Events Published:**
- `task.created`
- `task.leased`
- `task.completed`
- `task.failed`
- `task.lease_expired`

**Dependencies:**
- MySQL (task persistence)
- Redis (distributed lock, lease TTL)
- Event Service (publish task lifecycle events)
- Audit Service (async audit trail via events)

### 3.3 Event Service

**Responsibility:** Receives events from Python Agent, validates sequence continuity, deduplicates, persists, and ACKs. Notifies Task Service of state-relevant events.

**Data Ownership:**
- `task_events` table (sole writer)
- Redis keys: `event:dedup:{eventId}`, `event:seq:{agentId}`

**Inbound API:**
```
POST   /events                   # Ingest event from Python Agent
GET    /events?taskId={id}       # Query events for a task
GET    /events/{eventId}         # Get specific event
```

**Outbound:**
- ACK response: `{ seq, accepted, duplicate, errorCode }`
- Internal notification to Task Service on state-changing events

**Dependencies:**
- MySQL (event persistence)
- Redis (deduplication, sequence tracking)
- Task Service (notify on task state transitions)

### 3.4 Artifact Service

**Responsibility:** Stores generated code packages, serves them over HTTP, manages retention policies, and logs access events.

**Data Ownership:**
- `artifacts` table (sole writer)
- File storage (local filesystem or object storage)

**Inbound API:**
```
POST   /artifacts                # Upload artifact (from Python Agent or Task Service)
GET    /artifacts/{artifactId}   # Download artifact (ZIP)
GET    /artifacts/{artifactId}/metadata  # Get artifact metadata
DELETE /artifacts/{artifactId}   # Delete artifact (retention enforcement)
GET    /s/{shortCode}            # Short-link redirect
```

**Dependencies:**
- MySQL (artifact metadata)
- File storage backend
- Audit Service (async access logging via events)

### 3.5 Approval Service

**Responsibility:** Manages approval workflows for sensitive task operations. Enforces RBAC, project membership, and security gates.

**Data Ownership:**
- `approvals` table (sole writer)
- `users`, `user_roles`, `project_memberships` tables (shared with Auth, read-only for others)

**Inbound API:**
```
POST   /approvals                # Request approval for a task action
POST   /approvals/{id}/decide    # Submit approval decision
GET    /approvals?taskId={id}    # Query approvals for a task
GET    /projects/{id}/members    # Project membership management
```

**Dependencies:**
- MySQL (approval state, user/role data)
- Task Service (validate task exists before approval)
- Audit Service (async audit trail via events)

### 3.6 Audit Service

**Responsibility:** Receives audit events from all other services and persists an immutable compliance trail. Provides query API for audit log export.

**Data Ownership:**
- `audit_logs` table (sole writer, append-only)

**Inbound API:**
```
POST   /audit/events             # Ingest audit event (internal, from other services)
GET    /audit/logs               # Query audit logs (with filters)
GET    /audit/logs/export        # Export audit trail (CSV/JSON)
```

**Dependencies:**
- MySQL (audit log persistence)
- Message broker (consume audit events from other services)

---

## 4. Data Ownership Mapping

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ Service          │ Owned Tables                                         │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Task Service     │ tasks, idempotency_records                           │
│ Event Service    │ task_events                                          │
│ Artifact Service │ artifacts                                            │
│ Approval Service │ approvals, users, user_roles, project_memberships,  │
│                  │ projects                                             │
│ Audit Service    │ audit_logs                                           │
└──────────────────┴──────────────────────────────────────────────────────┘
```

**Cross-service data access rules:**
- Services MUST NOT directly query another service's database tables.
- Cross-service reads are performed via synchronous REST calls or async event consumption.
- Foreign key relationships that cross service boundaries are replaced with logical IDs (e.g., `taskId` as a string reference, not a DB foreign key).

---

## 5. Service Interface Contracts

### 5.1 Synchronous REST Contracts

All services expose REST APIs with:
- JSON request/response bodies
- Standard HTTP status codes (200, 201, 400, 404, 409, 500)
- `X-Request-ID` header for tracing
- `X-Idempotency-Key` header for mutation operations
- OpenAPI 3.0 specification published at `/v3/api-docs`

### 5.2 Asynchronous Event Contracts

Services communicate state changes via domain events on a shared message broker (RabbitMQ, existing infrastructure):

```
Exchange: autocode.events
Routing key pattern: {service}.{entity}.{action}

Examples:
  task.task.created
  task.task.completed
  event.event.received
  artifact.artifact.uploaded
  approval.approval.decided
  audit.log.written
```

Event envelope schema:
```json
{
  "eventId": "uuid",
  "eventType": "task.task.created",
  "timestamp": "ISO-8601",
  "sourceService": "task-service",
  "payload": { ... }
}
```

### 5.3 Health Check Contract

All services expose:
```
GET /actuator/health          # Spring Boot Actuator health
GET /actuator/prometheus      # Prometheus metrics scrape endpoint
```

---

## 6. Decomposition Sequence

Following Requirement 11.2 (Gateway → Event Services → Task Services → Artifact Services):

### Phase 1: Gateway (P1-2, already planned)
Extract Spring Cloud Gateway as the unified entry point. No business logic moves yet.

### Phase 2: Artifact Service (P2-1, first extraction)
Artifact Service is the lowest-coupling candidate:
- No synchronous dependencies from other services at runtime
- Self-contained hexagonal architecture already exists in `artifacts/`
- Can be extracted with a strangler-fig pattern: route `/artifacts/**` through gateway to new service

### Phase 3: Event Service (P2-1, second extraction)
Extract event ingestion and deduplication:
- `EventController` and `EventDeduplicationService` move to new service
- Task state transitions triggered by events become async (event → Task Service via message broker)

### Phase 4: Audit Service (P2-1, third extraction)
Extract audit trail as a pure consumer:
- All services publish audit events; Audit Service consumes and persists
- No synchronous callers depend on Audit Service at request time

### Phase 5: Task Service and Approval Service (P2-2+)
These are the most coupled and are extracted last:
- Task Service requires careful migration of the distributed lock and lease logic
- Approval Service requires user/role data migration

---

## 7. Migration Risk Assessment

| Service | Coupling Level | Data Migration Complexity | Recommended Phase |
|---|---|---|---|
| Artifact Service | Low | Low (self-contained) | P2-1 (first) |
| Event Service | Medium | Medium (dedup state in Redis) | P2-1 (second) |
| Audit Service | Low | Low (append-only, no consumers) | P2-1 (third) |
| Task Service | High | High (lock/lease/state machine) | P2-2 |
| Approval Service | Medium | Medium (user/role data shared) | P2-2 |

---

## 8. References

- Requirements: 11.1 (service boundary definition), 11.2 (migration order), 11.3 (canary deployment), 11.4 (backward compatibility), 11.5 (rollback procedures)
- Design: Properties 37 (Canary Deployment Support), 38 (Backward Compatibility), 39 (Performance Validation), 40 (Zero Downtime)
- Related docs: `backend-upgrade-master-plan-2026-04.md`, `adr-002-p2-platformization-gateway-observability.md`
