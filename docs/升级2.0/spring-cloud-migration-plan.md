# Spring Cloud Migration Blueprint

**Version:** 1.0  
**Date:** 2026-05  
**Scope:** Control Plane Spring → Spring Cloud Microservices  
**Validates: Requirements 11.2, 11.5**

---

## 1. Overview

This document defines the migration blueprint for evolving `control-plane-spring` from a Spring Boot monolith into a Spring Cloud microservices architecture. It covers service discovery, configuration management, the gradual migration sequence, and rollback procedures for each phase.

The migration follows the principle of **incremental extraction with zero downtime**, using the strangler-fig pattern: new services are introduced alongside the monolith, traffic is gradually shifted, and the monolith is hollowed out over time.

---

## 2. Spring Cloud Component Selection

### 2.1 Service Discovery: Spring Cloud Netflix Eureka

**Decision:** Use Eureka Server for service registration and discovery.

**Rationale:**
- Native Spring Cloud integration with minimal configuration
- Consistent with the existing Spring Boot ecosystem in `control-plane-spring`
- Self-preservation mode handles network partitions gracefully
- Simpler operational model than Consul for the current team size

**Alternative considered:** Consul — provides stronger consistency guarantees and health check flexibility, but adds operational complexity (Raft consensus, separate binary). Eureka is sufficient for the current scale.

**Eureka Server setup:**
```yaml
# eureka-server/src/main/resources/application.yml
server:
  port: 8761

eureka:
  instance:
    hostname: eureka-server
  client:
    register-with-eureka: false
    fetch-registry: false
  server:
    enable-self-preservation: true
    eviction-interval-timer-in-ms: 10000
```

**Client configuration (applied to all microservices):**
```yaml
eureka:
  client:
    service-url:
      defaultZone: http://eureka-server:8761/eureka/
  instance:
    prefer-ip-address: true
    lease-renewal-interval-in-seconds: 10
    lease-expiration-duration-in-seconds: 30
```

### 2.2 Configuration Management: Spring Cloud Config Server

**Decision:** Use Spring Cloud Config Server backed by a Git repository.

**Rationale:**
- Centralized configuration with environment-specific overrides (dev/staging/prod)
- Git history provides an audit trail for configuration changes
- Supports runtime refresh via `/actuator/refresh` without service restart
- Integrates with Spring Boot's `@Value` and `@ConfigurationProperties` — no code changes needed in services

**Config Server setup:**
```yaml
# config-server/src/main/resources/application.yml
server:
  port: 8888

spring:
  cloud:
    config:
      server:
        git:
          uri: ${CONFIG_REPO_URI:file://./config-repo}
          default-label: main
          search-paths: '{application}'
          clone-on-start: true
```

**Config repository structure:**
```
config-repo/
├── application.yml              # Shared defaults for all services
├── task-service/
│   ├── application.yml          # Task Service defaults
│   ├── application-staging.yml
│   └── application-prod.yml
├── event-service/
│   └── application.yml
├── artifact-service/
│   └── application.yml
├── approval-service/
│   └── application.yml
└── audit-service/
    └── application.yml
```

**Client bootstrap configuration:**
```yaml
# Each service's bootstrap.yml
spring:
  application:
    name: task-service          # Must match config-repo directory name
  config:
    import: "configserver:http://config-server:8888"
```

### 2.3 API Gateway: Spring Cloud Gateway

The Spring Cloud Gateway is already planned in task 19 and ADR-002. It serves as the unified entry point at port 8080 and handles routing, authentication header propagation, rate limiting, and timeout enforcement.

See `docs/升级2.0/adr-002-p2-platformization-gateway-observability.md` for the gateway decision rationale.

### 2.4 Inter-Service Communication

**Synchronous:** Spring Cloud OpenFeign for typed REST clients between services.

```java
// Example: Task Service calling Audit Service
@FeignClient(name = "audit-service")
public interface AuditServiceClient {
    @PostMapping("/audit/events")
    void publishAuditEvent(@RequestBody AuditEventRequest request);
}
```

**Asynchronous:** RabbitMQ (already in infrastructure) for domain events. Services publish events to exchanges; consumers subscribe to relevant routing keys.

**Circuit breaking:** Resilience4j (Spring Cloud Circuit Breaker) wraps all Feign clients and critical async consumers.

---

## 3. Infrastructure Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                     Spring Cloud Infrastructure                  │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐                       │
│  │ Eureka Server│    │  Config Server   │                       │
│  │  Port: 8761  │    │   Port: 8888     │                       │
│  └──────┬───────┘    └────────┬─────────┘                       │
│         │ (register)          │ (fetch config)                  │
│         ▼                     ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Spring Cloud Gateway  :8080                 │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │ (route)                           │
│         ┌───────────────────┼───────────────────┐              │
│         ▼                   ▼                   ▼              │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐      │
│  │Task Service │   │Event Service│   │Artifact Service  │      │
│  │  Port: 8061 │   │ Port: 8062  │   │   Port: 8063     │      │
│  └─────────────┘   └─────────────┘   └──────────────────┘      │
│         │                   │                   │              │
│  ┌─────────────┐   ┌─────────────────────────────────────┐      │
│  │Approval Svc │   │         Audit Service               │      │
│  │  Port: 8064 │   │          Port: 8065                 │      │
│  └─────────────┘   └─────────────────────────────────────┘      │
│                                                                 │
│  Shared: MySQL, Redis, RabbitMQ, Prometheus, Grafana            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Gradual Migration Sequence

The migration follows the service extraction order defined in `service-boundary-analysis.md` (Requirement 11.2: Gateway → Event Services → Task Services → Artifact Services).

### Phase 0: Infrastructure Bootstrap (Pre-migration)

**Goal:** Stand up Spring Cloud infrastructure without touching the monolith.

**Steps:**
1. Create `eureka-server/` Spring Boot application and add to `docker-compose.yml`
2. Create `config-server/` Spring Boot application with Git-backed config repo
3. Add Eureka client dependency to `control-plane-spring` — monolith registers itself
4. Verify monolith still functions normally with Eureka registration

**Validation criteria:**
- Eureka dashboard shows `control-plane-spring` registered
- Config Server serves `application.yml` to monolith
- All existing smoke tests pass

**Rollback:** Remove Eureka client dependency from monolith pom.xml. No data migration needed.

---

### Phase 1: Spring Cloud Gateway (P1-2)

**Goal:** Route all traffic through the gateway without changing monolith behavior.

**Steps:**
1. Create `ops/gateway-service/` Spring Cloud Gateway application
2. Configure routes: all `/**` → `control-plane-spring`
3. Add authentication header propagation filter
4. Add trace ID injection filter
5. Deploy gateway at port 8080; monolith remains at 8058

**Gateway routing configuration:**
```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: control-plane
          uri: lb://control-plane-spring
          predicates:
            - Path=/**
          filters:
            - PropagateAuthHeader
            - InjectTraceId
            - name: CircuitBreaker
              args:
                name: control-plane-cb
                fallbackUri: forward:/fallback
```

**Validation criteria:**
- All API calls through port 8080 return same responses as direct port 8058 calls
- Trace IDs appear in downstream service logs
- Gateway metrics visible in Prometheus

**Rollback:** Stop gateway service. Clients revert to direct port 8058 access.

---

### Phase 2: Artifact Service Extraction (P2-1, first)

**Goal:** Extract Artifact Service as the first independent microservice.

**Steps:**
1. Create `artifact-service/` Spring Boot application
2. Migrate `artifacts/` hexagonal domain, `ArtifactQueryService`, `ArtifactsController`, `ArtifactShortLinkController`
3. Migrate `artifacts` database table to artifact-service schema (or use schema-per-service with shared MySQL instance initially)
4. Register artifact-service with Eureka
5. Add gateway route: `/artifacts/**` and `/s/**` → `artifact-service`
6. Enable canary: route 5% of artifact traffic to new service
7. Monitor error rates and latency for 24 hours
8. Gradually increase to 20% → 50% → 100%
9. Remove artifact handling from monolith

**Feature flag configuration (in Config Server):**
```yaml
# config-repo/gateway-service/application.yml
routing:
  artifact-service:
    canary-weight: 5          # Percentage of traffic to new service
    enabled: true
```

**Validation criteria:**
- Artifact download success rate ≥ 99.5% (Requirement 14.7)
- P95 latency does not increase by more than 10%
- No artifact metadata loss during migration

**Rollback trigger:** If error rate exceeds 1% or P95 latency increases >20%, route 100% traffic back to monolith via gateway weight update (no deployment needed).

---

### Phase 3: Event Service Extraction (P2-1, second)

**Goal:** Extract Event Service with ACK semantics and deduplication.

**Steps:**
1. Create `event-service/` Spring Boot application
2. Migrate `EventController`, `EventDeduplicationService`, `EventAckResponse`
3. Migrate `task_events` table and Redis dedup keys
4. Task state transitions triggered by events become async: Event Service publishes `event.received` to RabbitMQ; Task Service (still in monolith) consumes
5. Add gateway route: `/events/**` → `event-service`
6. Canary rollout: 5% → 20% → 50% → 100%

**Validation criteria:**
- Event delivery failure rate < 0.01% (Requirement 2.7)
- Duplicate event rate remains 0%
- ACK response time < 100ms P95

**Rollback trigger:** Any event loss detected, or duplicate processing rate > 0.01%.

---

### Phase 4: Audit Service Extraction (P2-1, third)

**Goal:** Extract Audit Service as a pure event consumer.

**Steps:**
1. Create `audit-service/` Spring Boot application
2. Migrate `AuditService`, `AuditController`, `AuditLogEntity`
3. All other services publish `audit.event` messages to RabbitMQ; Audit Service consumes and persists
4. Remove synchronous `AuditService` calls from monolith; replace with async event publishing
5. Add gateway route: `/audit/**` → `audit-service`

**Validation criteria:**
- All task/event/artifact/approval actions produce audit log entries
- Audit log query API returns correct results
- No audit log gaps during migration window

**Rollback trigger:** Audit log gaps detected or audit query API error rate > 1%.

---

### Phase 5: Task Service Extraction (P2-2)

**Goal:** Extract the core Task Service — the most complex extraction.

**Steps:**
1. Create `task-service/` Spring Boot application
2. Migrate `TaskService`, `TaskController`, distributed lock/lease logic
3. Migrate `tasks`, `idempotency_records` tables
4. Migrate Redis lock keys (`task:lock:*`, `task:lease:*`)
5. Update Event Service to call Task Service via Feign for state transitions
6. Canary rollout with extended monitoring (48 hours at each stage)

**Validation criteria:**
- Duplicate task execution rate < 0.1% (Requirement 5.6)
- Task lease expiration and recovery works correctly
- Idempotency guarantees maintained across service boundary

**Rollback trigger:** Duplicate execution rate > 0.1%, or task state machine inconsistency detected.

---

### Phase 6: Approval Service Extraction (P2-2)

**Goal:** Extract Approval Service with RBAC and user management.

**Steps:**
1. Create `approval-service/` Spring Boot application
2. Migrate `ApprovalEntity`, `UserEntity`, `UserRoleEntity`, `ProjectEntity`, `ProjectMembershipEntity`
3. Migrate `AuthController`, `ProjectController`, approval workflow logic
4. Update `JwtSecurityConfig` in remaining services to validate JWT against Approval Service
5. Add gateway route: `/approvals/**`, `/projects/**`, `/auth/**` → `approval-service`

**Validation criteria:**
- RBAC enforcement works correctly across service boundary
- JWT validation succeeds for all authenticated requests
- Approval workflow completes end-to-end

**Rollback trigger:** Authentication failures > 0.1%, or RBAC bypass detected.

---

## 5. Rollback Procedures

### 5.1 General Rollback Principles

- **Gateway-level rollback:** Change routing weights in Config Server. Takes effect within 30 seconds (Spring Cloud Config refresh). No redeployment needed.
- **Service-level rollback:** Stop the new microservice container. Gateway falls back to monolith route.
- **Data rollback:** Each phase maintains backward-compatible schema changes. Destructive schema changes (dropping columns/tables) are deferred until the phase is fully validated.

### 5.2 Rollback Triggers (Automatic)

The following conditions trigger automatic rollback via gateway routing:

| Metric | Threshold | Action |
|---|---|---|
| Service error rate | > 1% over 5 minutes | Route 100% to monolith |
| P95 latency increase | > 20% vs baseline | Route 100% to monolith |
| Duplicate execution rate | > 0.1% | Route 100% to monolith |
| Event loss rate | > 0.01% | Route 100% to monolith |
| Health check failures | 3 consecutive | Remove from Eureka, route to monolith |

### 5.3 Manual Rollback Procedure

For any phase, the manual rollback steps are:

```bash
# Step 1: Update Config Server to route 100% traffic to monolith
# Edit config-repo/gateway-service/application.yml:
#   routing.<service-name>.canary-weight: 0

# Step 2: Trigger config refresh on gateway
curl -X POST http://gateway-service:8080/actuator/refresh

# Step 3: Verify traffic is back on monolith
curl http://gateway-service:8080/actuator/health

# Step 4: Stop the extracted microservice (optional, for investigation)
docker-compose stop <service-name>

# Step 5: Notify team and open incident ticket
```

### 5.4 Data Rollback

For phases involving database migration:
- Schema changes use Flyway migrations with `undo` scripts prepared in advance
- Data written to the new service's schema is replicated back to the monolith schema during the canary period (dual-write)
- Dual-write is disabled only after the phase is fully validated and the rollback window has passed (minimum 72 hours)

---

## 6. Configuration Management Strategy

### 6.1 Environment Promotion

Configuration flows through environments:

```
dev → staging → prod
```

Each environment has its own Config Server profile. Promotion is done via Git branch merge:
- `dev` branch → development environment
- `main` branch → staging and production (with environment-specific overrides)

### 6.2 Secret Management

Secrets (database passwords, JWT signing keys, Redis passwords) are NOT stored in the Config Server Git repository. They are injected via:
- Docker Compose environment variables (development)
- Kubernetes Secrets or AWS Secrets Manager (production)

Config Server references secrets via `${ENV_VAR}` placeholders.

### 6.3 Runtime Configuration Refresh

Services support runtime configuration refresh without restart:

```bash
# Refresh a specific service instance
curl -X POST http://<service-host>:<port>/actuator/refresh

# Refresh all instances of a service via Spring Cloud Bus (future enhancement)
curl -X POST http://config-server:8888/actuator/busrefresh/<service-name>
```

Properties annotated with `@RefreshScope` are re-evaluated on refresh. This enables:
- Canary weight adjustments without redeployment
- Feature flag toggling
- Timeout and rate limit tuning

---

## 7. Observability During Migration

### 7.1 Metrics to Monitor Per Phase

Each extraction phase adds the following Prometheus metrics:

```
# Service registration
eureka_client_registered_replicas_gauge
eureka_client_instances_delta_gauge

# Per-service health
up{job="<service-name>"}

# Request routing (gateway)
spring_cloud_gateway_requests_seconds_count{routeId="<route>", status="200"}
spring_cloud_gateway_requests_seconds_count{routeId="<route>", status="5xx"}

# Circuit breaker state
resilience4j_circuitbreaker_state{name="<service>-cb"}
```

### 7.2 Grafana Dashboard

A dedicated "Migration Progress" Grafana dashboard tracks:
- Traffic split between monolith and each extracted service (canary weight vs actual traffic)
- Error rate comparison: monolith vs new service
- P95 latency comparison
- Circuit breaker state per service

### 7.3 Alerting Rules

```yaml
# Prometheus alert rules for migration
groups:
  - name: migration
    rules:
      - alert: MicroserviceHighErrorRate
        expr: |
          rate(spring_cloud_gateway_requests_seconds_count{status=~"5.."}[5m])
          / rate(spring_cloud_gateway_requests_seconds_count[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Microservice {{ $labels.routeId }} error rate > 1%"
          action: "Trigger rollback procedure"

      - alert: MicroserviceLatencyIncrease
        expr: |
          histogram_quantile(0.95, rate(spring_cloud_gateway_requests_seconds_bucket[5m]))
          > 1.2 * histogram_quantile(0.95, rate(spring_cloud_gateway_requests_seconds_bucket[5m] offset 1h))
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency increased >20% for {{ $labels.routeId }}"
```

---

## 8. Migration Timeline

| Phase | Task | Duration | Dependencies |
|---|---|---|---|
| Phase 0 | Infrastructure bootstrap (Eureka + Config Server) | 1 week | None |
| Phase 1 | Spring Cloud Gateway (P1-2) | 1 week | Phase 0 |
| Phase 2 | Artifact Service extraction (P2-1) | 2 weeks | Phase 1 |
| Phase 3 | Event Service extraction (P2-1) | 2 weeks | Phase 2 |
| Phase 4 | Audit Service extraction (P2-1) | 1 week | Phase 3 |
| Phase 5 | Task Service extraction (P2-2) | 3 weeks | Phase 4 |
| Phase 6 | Approval Service extraction (P2-2) | 2 weeks | Phase 5 |

Total estimated duration: ~12 weeks from Phase 0 start.

---

## 9. Success Criteria

The migration is considered complete when:

1. All five microservices are running independently and registered with Eureka
2. The monolith `control-plane-spring` handles only legacy compatibility routes (if any)
3. Post-migration performance meets or exceeds baseline (Requirement 11.6):
   - Task creation P95 latency ≤ pre-migration baseline
   - Event delivery failure rate < 0.01%
   - Artifact download success rate ≥ 99.5%
4. Zero downtime achieved throughout the migration (Requirement 11.7)
5. All existing API contracts maintained (Requirement 11.4)
6. Rollback procedures tested and documented for each phase

---

## 10. References

- Requirements: 11.1 (service boundaries), 11.2 (migration order), 11.3 (canary deployment), 11.4 (backward compatibility), 11.5 (rollback procedures), 11.6 (performance validation), 11.7 (zero downtime)
- Design: Properties 37–40 (canary, backward compatibility, performance, zero downtime)
- Related docs:
  - `service-boundary-analysis.md` — service boundary definitions and data ownership
  - `adr-002-p2-platformization-gateway-observability.md` — gateway decision rationale
  - `backend-upgrade-master-plan-2026-04.md` — overall upgrade strategy
