# Canary Deployment Strategy — Backend Upgrade 2.0

**Validates: Requirements 11.3, 11.4, 11.6, 11.7**

## Overview

This document defines the canary deployment strategy for the Backend Upgrade 2.0 project. The strategy ensures gradual, safe rollout of framework upgrades while maintaining zero downtime for critical user-facing functionality and preserving backward compatibility for existing APIs.

The approach uses feature flags backed by Redis to control traffic routing, combined with automated health checks and performance validation to trigger rollbacks when needed.

---

## Rollout Phases

Each upgrade component (LangGraph engine, Spring Cloud Gateway, microservice extraction) follows the same five-phase rollout pattern.

```
Phase 0 (Baseline)  →  Phase 1 (Canary 5%)  →  Phase 2 (Canary 25%)
    →  Phase 3 (Canary 50%)  →  Phase 4 (Full Rollout 100%)
```

### Phase 0 — Baseline (0% new, 100% legacy)

- All traffic routes to the existing V1 system.
- Baseline performance metrics are captured: P95 latency, throughput (req/s), error rate.
- Feature flags are created in Redis but set to `enabled=False`.
- Smoke tests confirm the V1 system is healthy before any traffic is shifted.

**Exit criteria:** All smoke tests pass; baseline metrics recorded.

### Phase 1 — Canary (5%)

- Feature flag `canary_percentage` set to `5`.
- 5% of task IDs (determined by consistent hash) are routed to the new component.
- Monitor for 30 minutes minimum before advancing.
- Automated rollback triggers active (see §Automated Rollback Triggers).

**Exit criteria:** Error rate ≤ baseline + 0.5%; P95 latency ≤ baseline × 1.1; no critical alerts.

### Phase 2 — Canary (25%)

- `canary_percentage` increased to `25`.
- Monitor for 1 hour minimum.
- Compare performance metrics against baseline.

**Exit criteria:** Error rate ≤ baseline + 0.5%; P95 latency ≤ baseline × 1.1; throughput ≥ baseline × 0.95.

### Phase 3 — Canary (50%)

- `canary_percentage` increased to `50`.
- Monitor for 2 hours minimum.
- Full load comparison between old and new paths.

**Exit criteria:** All Phase 2 criteria met; no memory leaks detected; connection pool utilisation < 80%.

### Phase 4 — Full Rollout (100%)

- `canary_percentage` set to `100` (or `enabled=True` with no canary split).
- Legacy path remains available for emergency rollback for 24 hours.
- After 24 hours of stable operation, legacy code can be removed.

**Exit criteria:** 24 hours of stable operation; all performance criteria met.

---

## Feature Flag Implementation

Feature flags are stored in Redis and managed by `python-agent/utils/feature_flags.py`. Each flag controls one upgrade component.

### Available Flags

| Flag | Component | Default |
|------|-----------|---------|
| `LANGGRAPH_ENGINE` | LangGraph orchestration engine | disabled |
| `NEW_BACKEND_GENERATOR` | Enhanced Flask/FastAPI generator | disabled |
| `SPRING_CLOUD_GATEWAY` | Spring Cloud Gateway routing | disabled |
| `ARTIFACT_MICROSERVICE` | Extracted Artifact Service | disabled |
| `EVENT_MICROSERVICE` | Extracted Event Service | disabled |
| `APPROVAL_MICROSERVICE` | Extracted Approval Service | disabled |
| `NEW_VALIDATION_GATE` | Enhanced validation gate | disabled |
| `DISTRIBUTED_LOCK_V2` | Updated distributed lock implementation | disabled |

### Routing Logic

Traffic routing uses a consistent hash of the `task_id` modulo 100 to determine which percentage bucket a request falls into. This ensures:

- The same task always routes to the same component (no mid-task switching).
- Traffic split is stable across restarts.
- No session affinity infrastructure is required.

```python
bucket = int(hashlib.md5(task_id.encode()).hexdigest(), 16) % 100
route_to_new = bucket < canary_percentage
```

### Redis Key Schema

```
feature_flag:{flag_name}:enabled          → "true" | "false"
feature_flag:{flag_name}:canary_percentage → "0" – "100"
feature_flag:{flag_name}:updated_at        → ISO-8601 timestamp
feature_flag:{flag_name}:updated_by        → operator identifier
```

---

## Rollback Procedures

### Immediate Rollback (Any Phase)

Run `scripts/rollback.sh rollback <component>` to instantly disable a feature flag and route all traffic back to the legacy path. This takes effect within seconds (next Redis read).

```bash
# Example: roll back LangGraph engine
./scripts/rollback.sh rollback langgraph_engine
```

No restart of any service is required. The rollback is purely a Redis flag update.

### Phase-Specific Rollback Procedures

#### Phase 1 → Phase 0 Rollback

1. Set `canary_percentage` to `0` (or `enabled=False`).
2. Verify all in-flight tasks complete on the legacy path.
3. Capture error logs from the canary period for root cause analysis.
4. Alert the on-call team via Alertmanager.

#### Phase 2 → Phase 1 Rollback

1. Reduce `canary_percentage` from `25` to `5`.
2. Monitor for 15 minutes to confirm stabilisation.
3. If issues persist, roll back to Phase 0.

#### Phase 3 → Phase 2 Rollback

1. Reduce `canary_percentage` from `50` to `25`.
2. Monitor for 30 minutes.
3. If issues persist, reduce to `5` or `0`.

#### Phase 4 → Phase 3 Rollback

1. Set `canary_percentage` to `50`.
2. If legacy code has not yet been removed, traffic immediately splits.
3. If legacy code was removed, a hotfix deployment is required — escalate immediately.

### Post-Rollback Actions

1. Capture a snapshot of Prometheus metrics at rollback time.
2. File an incident report with: rollback trigger, affected phase, metrics at time of rollback.
3. Conduct a root cause analysis before re-attempting the rollout.
4. Update the rollout plan with lessons learned.

---

## Performance Validation Criteria

Post-upgrade performance must meet or exceed baseline metrics before advancing to the next phase.

### Thresholds

| Metric | Threshold | Measurement Window |
|--------|-----------|-------------------|
| P95 API latency | ≤ baseline × 1.10 | 5-minute rolling window |
| P99 API latency | ≤ baseline × 1.20 | 5-minute rolling window |
| Request throughput | ≥ baseline × 0.95 | 5-minute rolling window |
| Error rate | ≤ baseline + 0.5% | 5-minute rolling window |
| Task success rate | ≥ 90% | 10-minute rolling window |
| Backend generation success | ≥ 90% | 10-minute rolling window |
| Redis cache hit rate | ≥ 95% | 10-minute rolling window |
| DB connection pool utilisation | ≤ 80% | 5-minute rolling window |

### Baseline Capture

Before starting any rollout, run the baseline capture script:

```bash
./scripts/canary-rollout.sh capture-baseline <component>
```

This records current Prometheus metrics to `scripts/baselines/<component>-baseline.json`.

### Validation Script

```bash
./scripts/canary-rollout.sh validate-performance <component>
```

Compares current metrics against the stored baseline and exits non-zero if any threshold is breached.

---

## Automated Rollback Triggers

The following conditions trigger an automatic rollback without human intervention.

### Trigger Conditions

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Error rate spike | > baseline + 2% for 2 consecutive minutes | Rollback to previous phase |
| P95 latency spike | > baseline × 1.5 for 2 consecutive minutes | Rollback to previous phase |
| Task success rate drop | < 85% for 5 minutes | Rollback to previous phase |
| Health check failure | 3 consecutive failures | Rollback to Phase 0 |
| OOM / crash loop | Any pod restart in canary path | Rollback to previous phase |

### Implementation

Automated rollback is implemented as a Prometheus alerting rule that calls the rollback script via Alertmanager webhook:

```yaml
# prometheus/rules/canary-rollback.yml
groups:
  - name: canary_rollback
    rules:
      - alert: CanaryErrorRateSpike
        expr: |
          (
            rate(http_requests_total{status=~"5.."}[2m])
            / rate(http_requests_total[2m])
          ) > (canary_baseline_error_rate + 0.02)
        for: 2m
        labels:
          severity: critical
          action: rollback
        annotations:
          summary: "Canary error rate spike — triggering rollback"
          component: "{{ $labels.component }}"

      - alert: CanaryLatencySpike
        expr: |
          histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[2m]))
          > (canary_baseline_p95_latency * 1.5)
        for: 2m
        labels:
          severity: critical
          action: rollback
        annotations:
          summary: "Canary P95 latency spike — triggering rollback"
```

Alertmanager routes `action: rollback` alerts to a webhook receiver that calls:

```bash
./scripts/rollback.sh auto-rollback <component>
```

---

## Zero Downtime Guarantee

To ensure zero downtime during upgrades (Requirement 11.7):

1. **No hard cutovers**: Traffic is never switched 0% → 100% in a single step.
2. **In-flight task protection**: Tasks already running on the legacy path complete on the legacy path. The feature flag check happens only at task dispatch time.
3. **Health check gate**: `canary-rollout.sh increase-traffic` refuses to increase traffic if health checks are failing.
4. **Dual-path availability**: Both legacy and new paths remain operational throughout the rollout. The legacy path is only decommissioned after 24 hours of stable 100% rollout.
5. **Stateless flag evaluation**: Feature flag reads are non-blocking Redis GET operations with a 100ms timeout. If Redis is unavailable, the system defaults to the legacy path.

---

## Backward Compatibility Requirements

All new components must maintain backward compatibility for existing APIs (Requirement 11.4):

- **API contracts**: No breaking changes to existing REST endpoints. New fields may be added; existing fields must not be removed or renamed.
- **Event schema**: Event payloads must remain backward compatible. New optional fields are allowed.
- **Database schema**: Migrations must be additive (add columns/tables only). No column renames or drops during the rollout window.
- **Configuration**: New configuration keys must have sensible defaults so existing deployments work without changes.

Backward compatibility is validated by running the existing integration test suite against the new component before advancing to Phase 2.

---

## Rollout Runbook

### Starting a Canary Rollout

```bash
# 1. Capture baseline metrics
./scripts/canary-rollout.sh capture-baseline <component>

# 2. Start canary at 5%
./scripts/canary-rollout.sh start-canary <component>

# 3. Monitor for 30 minutes, then validate
./scripts/canary-rollout.sh validate-performance <component>

# 4. Increase to 25%
./scripts/canary-rollout.sh increase-traffic <component> 25

# 5. Monitor for 1 hour, then validate
./scripts/canary-rollout.sh validate-performance <component>

# 6. Increase to 50%
./scripts/canary-rollout.sh increase-traffic <component> 50

# 7. Monitor for 2 hours, then validate
./scripts/canary-rollout.sh validate-performance <component>

# 8. Complete rollout
./scripts/canary-rollout.sh complete-rollout <component>
```

### Emergency Rollback

```bash
./scripts/rollback.sh rollback <component>
```

### Checking Current State

```bash
./scripts/canary-rollout.sh status <component>
```

---

## Component-Specific Notes

### LangGraph Engine (`LANGGRAPH_ENGINE`)

- Dual-engine comparison testing must pass before advancing past Phase 1.
- Output consistency between legacy and LangGraph engines is validated by `test_engine_consistency.py`.
- Rollback is instant: the orchestrator reads the flag on each task dispatch.

### Spring Cloud Gateway (`SPRING_CLOUD_GATEWAY`)

- DNS/load balancer change is required to route traffic through the gateway.
- Canary is implemented at the load balancer level (weighted routing) rather than in application code.
- The feature flag controls whether the gateway is in the routing path.

### Microservice Extraction (Artifact, Event, Approval)

- The Control Plane monolith and the extracted microservice run simultaneously during rollout.
- The feature flag controls which implementation handles each request.
- Database migrations must be applied to both the monolith schema and the microservice schema before starting the rollout.
