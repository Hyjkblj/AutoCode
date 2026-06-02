# ops/gateway-service

> **Note:** The Spring Cloud Gateway implementation lives in the Maven module at
> [`/gateway-service/`](../../gateway-service/) (root of the repository).
>
> This directory exists as a reference pointer. The actual source code,
> configuration, and Dockerfile are in the root `gateway-service/` module,
> which is declared in the parent `pom.xml`.

## Module Location

```
gateway-service/
├── Dockerfile
├── pom.xml
└── src/
    └── main/
        ├── java/com/autocode/gateway/
        │   ├── GatewayApplication.java          # Spring Boot entry point
        │   ├── config/
        │   │   ├── GatewayConfig.java           # Programmatic route configuration
        │   │   └── RateLimitConfig.java         # KeyResolver bean for rate limiting
        │   ├── filter/
        │   │   ├── TraceIdFilter.java           # Trace ID + W3C traceparent propagation
        │   │   ├── AuthHeaderPropagationFilter.java  # Auth header forwarding
        │   │   ├── TimeoutFilter.java           # 30s API / 300s generation timeouts
        │   │   ├── RateLimitingFilter.java      # 100 req/min per client (Redis-backed)
        │   │   └── ErrorHandlingFilter.java     # Upstream failure → structured JSON error
        │   └── health/
        │       └── GatewayHealthIndicator.java  # Upstream health checks
        └── resources/
            └── application.yml                  # Route + Redis + management config
```

## Routes

| Route ID                    | Path Pattern                                    | Upstream                  | Timeout |
|-----------------------------|------------------------------------------------|---------------------------|---------|
| `control-plane-generation`  | `/api/tasks/generate/**`, `/api/generate/**`   | Control Plane `:8058`     | 300 s   |
| `control-plane-api`         | `/api/**`                                      | Control Plane `:8058`     | 30 s    |
| `control-plane-ws`          | `/ws/**`                                       | Control Plane `:8058`     | none    |
| `control-plane-actuator`    | `/actuator/**`                                 | Control Plane `:8058`     | 30 s    |
| `artifact-shortlinks`       | `/s/**`                                        | Control Plane `:8058`     | 30 s    |
| `java-sandbox`              | `/sandbox/**`                                  | Java Sandbox `:18080`     | 30 s    |
| `static-content`            | `/static/**`, `/assets/**`                     | Static host               | 30 s    |
| `gateway-health`            | `/healthz`                                     | Local (no upstream)       | —       |

## Requirements Coverage

| Requirement | Description                                          | Implementation                          |
|-------------|------------------------------------------------------|-----------------------------------------|
| 9.1         | Unified entry point at port 8080                     | `server.port=8080` in `application.yml` |
| 9.2         | Route to Control Plane, Java Sandbox, static content | `GatewayConfig.java` route definitions  |
| 9.3         | Propagate trace IDs and auth headers                 | `TraceIdFilter`, `AuthHeaderPropagationFilter` |
| 9.4         | Timeout policies (30s API, 300s generation)          | `TimeoutFilter`                         |
| 9.5         | Rate limiting (100 req/min per client)               | `RateLimitingFilter` + `RateLimitConfig` |
| 9.6         | Error responses for upstream failures                | `ErrorHandlingFilter`                   |
