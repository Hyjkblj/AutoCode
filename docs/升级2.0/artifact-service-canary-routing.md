# Artifact Service Canary Routing

## Overview

This document describes the canary deployment strategy for migrating artifact
storage from the Control Plane monolith to the standalone `artifact-service`
microservice.

**Validates: Requirements 11.3, 11.6, 11.7**

## Feature Flag

The `ARTIFACT_MICROSERVICE` feature flag (defined in
`python-agent/utils/feature_flags.py`) controls traffic routing:

```python
from utils.feature_flags import FeatureFlag, FeatureFlagManager

manager = FeatureFlagManager(redis_client)

# Start canary at 5%
manager.set_flag(FeatureFlag.ARTIFACT_MICROSERVICE, enabled=True, canary_percentage=5)

# Check routing for a specific task
if manager.is_enabled(FeatureFlag.ARTIFACT_MICROSERVICE, task_id="task-abc"):
    # Route to artifact-service (port 8081)
    artifact_url = "http://artifact-service:8081"
else:
    # Route to Control Plane monolith (port 8058)
    artifact_url = "http://control-plane:8058"
```

## Rollout Phases

| Phase | Traffic % | Duration | Validation |
|-------|-----------|----------|------------|
| 0 | 0% | Baseline | Capture metrics |
| 1 | 5% | 30 min | Error rate, latency |
| 2 | 25% | 1 hour | Full metrics comparison |
| 3 | 50% | 2 hours | Load comparison |
| 4 | 100% | 24 hours | Final validation |

## Rollback

```bash
./scripts/rollback.sh rollback artifact_microservice
```

## Gateway Routing

The Spring Cloud Gateway routes artifact requests based on the feature flag.
When `ARTIFACT_MICROSERVICE` is enabled, the gateway routes `/api/v1/tasks/*/artifacts/**`
to `artifact-service:8081` instead of `control-plane:8058`.

Add to `gateway-service/src/main/resources/application.yml`:

```yaml
# Artifact microservice route (enabled when ARTIFACT_MICROSERVICE flag is active)
- id: artifact-microservice
  uri: ${ARTIFACT_SERVICE_URL:http://localhost:8081}
  predicates:
    - Path=/api/v1/tasks/*/artifacts/**
    - Header=X-Route-Artifact-Microservice, true
  filters:
    - AddRequestHeader=X-Gateway-Source, spring-cloud-gateway
```

The gateway checks the feature flag via a custom filter and adds the
`X-Route-Artifact-Microservice: true` header when the flag is enabled for
the requesting task.
