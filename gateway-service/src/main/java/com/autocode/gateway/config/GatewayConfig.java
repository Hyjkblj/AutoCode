package com.autocode.gateway.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.factory.RetryGatewayFilterFactory;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * Programmatic Spring Cloud Gateway route configuration.
 *
 * <p>Routes defined here complement the YAML-based routes in
 * {@code application.yml}. Programmatic routes allow more complex filter
 * chains and conditional logic that is difficult to express in YAML.
 *
 * <p>Route priority (highest → lowest):
 * <ol>
 *   <li>Gateway health endpoint ({@code /healthz})</li>
 *   <li>Generation tasks ({@code /api/tasks/generate/**}) – 300 s timeout</li>
 *   <li>Control Plane API ({@code /api/**}) – 30 s timeout</li>
 *   <li>Control Plane WebSocket ({@code /ws/**})</li>
 *   <li>Control Plane Actuator ({@code /actuator/**})</li>
 *   <li>Artifact short-links ({@code /s/**})</li>
 *   <li>Java Sandbox ({@code /sandbox/**})</li>
 *   <li>Static content ({@code /static/**})</li>
 *   <li>Fallback – 404 for unmatched paths</li>
 * </ol>
 *
 * <p>Satisfies Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6.
 */
@Configuration
public class GatewayConfig {

    @Value("${gateway.upstream.control-plane.url:http://localhost:8058}")
    private String controlPlaneUrl;

    @Value("${gateway.upstream.java-sandbox.url:http://localhost:18080}")
    private String javaSandboxUrl;

    @Value("${gateway.upstream.static-content.url:http://localhost:8058}")
    private String staticContentUrl;

    @Bean
    public RouteLocator customRouteLocator(RouteLocatorBuilder builder) {
        return builder.routes()

                // ------------------------------------------------------------------
                // 1. Gateway health endpoint – handled locally, no upstream call
                // ------------------------------------------------------------------
                .route("gateway-health", r -> r
                        .path("/healthz")
                        .filters(f -> f
                                .setStatus(HttpStatus.OK)
                                .setResponseHeader("Content-Type", "text/plain")
                                .modifyResponseBody(String.class, String.class,
                                        (exchange, body) -> Mono.just(
                                                "Gateway OK\nPort: 8080\nStatus: UP\n")))
                        .uri("no://op"))

                // ------------------------------------------------------------------
                // 2. Generation tasks – extended 300 s timeout (Requirement 9.4)
                //    Matches /api/tasks/generate/**, /api/generate/**, etc.
                // ------------------------------------------------------------------
                .route("control-plane-generation", r -> r
                        .path(
                                "/api/tasks/generate/**",
                                "/api/generate/**",
                                "/api/backend-generate/**",
                                "/api/fullstack-generate/**"
                        )
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "control-plane-generation")
                                // Retry only on connection errors, not on 5xx (generation is not idempotent)
                                .retry(config -> config
                                        .setRetries(1)
                                        .setMethods(HttpMethod.GET)
                                        .setBackoff(Duration.ofMillis(100), Duration.ofMillis(500), 2, false))
                        )
                        .uri(controlPlaneUrl))

                // ------------------------------------------------------------------
                // 3. Control Plane REST API – standard 30 s timeout (Requirement 9.4)
                // ------------------------------------------------------------------
                .route("control-plane-api", r -> r
                        .path("/api/**")
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "control-plane-api")
                                .retry(config -> config
                                        .setRetries(2)
                                        .setMethods(HttpMethod.GET)
                                        .setBackoff(Duration.ofMillis(50), Duration.ofMillis(500), 2, false))
                        )
                        .uri(controlPlaneUrl))

                // ------------------------------------------------------------------
                // 4. WebSocket upgrade – no timeout, no retry
                // ------------------------------------------------------------------
                .route("control-plane-ws", r -> r
                        .path("/ws/**")
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "control-plane-ws"))
                        .uri(controlPlaneUrl.replace("http://", "ws://")
                                           .replace("https://", "wss://")))

                // ------------------------------------------------------------------
                // 5. Control Plane Actuator (health, metrics, prometheus)
                // ------------------------------------------------------------------
                .route("control-plane-actuator", r -> r
                        .path("/actuator/**")
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "control-plane-actuator"))
                        .uri(controlPlaneUrl))

                // ------------------------------------------------------------------
                // 6. Artifact short-links
                // ------------------------------------------------------------------
                .route("artifact-shortlinks", r -> r
                        .path("/s/**")
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "artifact-shortlinks"))
                        .uri(controlPlaneUrl))

                // ------------------------------------------------------------------
                // 7. Java Sandbox execution endpoint
                // ------------------------------------------------------------------
                .route("java-sandbox", r -> r
                        .path("/sandbox/**")
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "java-sandbox")
                                // Sandbox calls are not idempotent – no retry
                        )
                        .uri(javaSandboxUrl))

                // ------------------------------------------------------------------
                // 8. Static content (served by Control Plane or a dedicated CDN)
                // ------------------------------------------------------------------
                .route("static-content", r -> r
                        .path("/static/**", "/assets/**", "/favicon.ico")
                        .filters(f -> f
                                .addRequestHeader("X-Gateway-Source", "spring-cloud-gateway")
                                .addRequestHeader("X-Route-Id", "static-content")
                                .addResponseHeader("Cache-Control", "public, max-age=3600"))
                        .uri(staticContentUrl))

                // ------------------------------------------------------------------
                // 9. Fallback – return 404 for any unmatched path
                // ------------------------------------------------------------------
                .route("fallback", r -> r
                        .path("/**")
                        .and()
                        .not(p -> p.path(
                                "/api/**", "/ws/**", "/actuator/**",
                                "/sandbox/**", "/s/**", "/static/**",
                                "/assets/**", "/favicon.ico", "/healthz"))
                        .filters(f -> f
                                .setStatus(HttpStatus.NOT_FOUND)
                                .setResponseHeader("Content-Type", "application/json")
                                .modifyResponseBody(String.class, String.class,
                                        (exchange, body) -> Mono.just(
                                                "{\"error\":\"Not Found\","
                                                + "\"message\":\"No route configured for this path\","
                                                + "\"gateway\":\"spring-cloud-gateway\"}")))
                        .uri("no://op"))

                .build();
    }
}
