package com.autocode.gateway.filter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.TimeoutException;

/**
 * Global filter that enforces per-route timeout policies.
 *
 * <p>Timeout rules (Requirement 9.4):
 * <ul>
 *   <li>Generation tasks ({@code /api/tasks/generate/**}, {@code /api/generate/**}):
 *       300 seconds</li>
 *   <li>All other API calls: 30 seconds</li>
 * </ul>
 *
 * <p>When a timeout fires the filter returns HTTP 504 Gateway Timeout with a
 * structured JSON body so callers can distinguish gateway timeouts from
 * upstream application errors.
 */
@Component
public class TimeoutFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(TimeoutFilter.class);

    /** Timeout for long-running generation tasks (Requirement 9.4). */
    static final Duration GENERATION_TIMEOUT = Duration.ofSeconds(300);

    /** Default timeout for regular API calls (Requirement 9.4). */
    static final Duration API_TIMEOUT = Duration.ofSeconds(30);

    /** Path prefixes that are subject to the extended generation timeout. */
    private static final String[] GENERATION_PATHS = {
            "/api/tasks/generate",
            "/api/generate",
            "/api/backend-generate",
            "/api/fullstack-generate"
    };

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 2;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getPath().value();
        Duration timeout = resolveTimeout(path);

        log.debug("Applying timeout {} for path '{}'", timeout, path);

        return chain.filter(exchange)
                .timeout(timeout)
                .onErrorResume(TimeoutException.class, ex -> handleTimeout(exchange, path, timeout));
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Selects the appropriate timeout based on the request path.
     */
    Duration resolveTimeout(String path) {
        for (String prefix : GENERATION_PATHS) {
            if (path.startsWith(prefix)) {
                return GENERATION_TIMEOUT;
            }
        }
        return API_TIMEOUT;
    }

    private Mono<Void> handleTimeout(ServerWebExchange exchange, String path, Duration timeout) {
        log.warn("Request timed out after {} for path '{}'", timeout, path);

        String traceId = exchange.getRequest().getHeaders().getFirst("X-Trace-Id");
        String body = buildTimeoutBody(path, timeout, traceId);

        exchange.getResponse().setStatusCode(HttpStatus.GATEWAY_TIMEOUT);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);

        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        return exchange.getResponse().writeWith(
                Mono.just(exchange.getResponse().bufferFactory().wrap(bytes))
        );
    }

    private String buildTimeoutBody(String path, Duration timeout, String traceId) {
        String traceField = traceId != null
                ? String.format(",\"traceId\":\"%s\"", traceId)
                : "";
        return String.format(
                "{\"error\":\"Gateway Timeout\","
                + "\"message\":\"Upstream service did not respond within %d seconds\","
                + "\"path\":\"%s\","
                + "\"timeoutSeconds\":%d"
                + "%s}",
                timeout.getSeconds(), path, timeout.getSeconds(), traceField
        );
    }
}
