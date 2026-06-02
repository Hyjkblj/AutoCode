package com.autocode.gateway.filter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.net.ConnectException;
import java.nio.charset.StandardCharsets;

/**
 * Global filter that catches upstream failures and returns structured error
 * responses to callers.
 *
 * <p>Satisfies Requirement 9.6: WHEN upstream services are unavailable, the
 * Spring_Cloud_Gateway SHALL return appropriate error responses.
 *
 * <p>Error mapping:
 * <ul>
 *   <li>{@link ConnectException} / connection refused → 503 Service Unavailable</li>
 *   <li>{@link java.util.concurrent.TimeoutException} → 504 Gateway Timeout
 *       (also handled by {@link TimeoutFilter}, kept here as safety net)</li>
 *   <li>5xx from upstream → 502 Bad Gateway</li>
 *   <li>Any other unexpected exception → 500 Internal Server Error</li>
 * </ul>
 *
 * <p>All error responses include a JSON body with {@code error}, {@code message},
 * {@code path}, and optionally {@code traceId} fields for easy client-side
 * diagnosis.
 */
@Component
public class ErrorHandlingFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(ErrorHandlingFilter.class);

    /** Run last so all other filters have a chance to handle the request first. */
    @Override
    public int getOrder() {
        return Ordered.LOWEST_PRECEDENCE - 10;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        return chain.filter(exchange)
                .onErrorResume(ex -> handleError(exchange, ex));
    }

    // -------------------------------------------------------------------------
    // Error handling
    // -------------------------------------------------------------------------

    private Mono<Void> handleError(ServerWebExchange exchange, Throwable ex) {
        String path = exchange.getRequest().getPath().value();
        String traceId = exchange.getRequest().getHeaders().getFirst("X-Trace-Id");

        ErrorInfo info = classify(ex);

        log.error("Gateway error [{}] for path '{}' traceId='{}': {}",
                info.status, path, traceId, ex.getMessage());

        if (exchange.getResponse().isCommitted()) {
            log.warn("Response already committed, cannot write error body for path '{}'", path);
            return Mono.error(ex);
        }

        exchange.getResponse().setStatusCode(info.status);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);

        String body = buildErrorBody(info, path, traceId);
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        return exchange.getResponse().writeWith(
                Mono.just(exchange.getResponse().bufferFactory().wrap(bytes))
        );
    }

    /**
     * Maps an exception to an HTTP status and a human-readable message.
     */
    private ErrorInfo classify(Throwable ex) {
        // Connection-level failures → upstream is down
        if (ex instanceof ConnectException
                || (ex.getCause() instanceof ConnectException)
                || ex.getMessage() != null && ex.getMessage().contains("Connection refused")) {
            return new ErrorInfo(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Upstream service is unavailable",
                    "SERVICE_UNAVAILABLE"
            );
        }

        // Timeout (safety net – TimeoutFilter handles most cases)
        if (ex instanceof java.util.concurrent.TimeoutException) {
            return new ErrorInfo(
                    HttpStatus.GATEWAY_TIMEOUT,
                    "Upstream service did not respond in time",
                    "GATEWAY_TIMEOUT"
            );
        }

        // Upstream returned a 5xx
        if (ex instanceof WebClientResponseException wcre) {
            if (wcre.getStatusCode().is5xxServerError()) {
                return new ErrorInfo(
                        HttpStatus.BAD_GATEWAY,
                        "Upstream service returned an error: " + wcre.getStatusCode(),
                        "BAD_GATEWAY"
                );
            }
        }

        // Spring's own response-status exceptions (e.g. from route predicates)
        if (ex instanceof ResponseStatusException rse) {
            return new ErrorInfo(
                    (HttpStatus) rse.getStatusCode(),
                    rse.getReason() != null ? rse.getReason() : "Request error",
                    "REQUEST_ERROR"
            );
        }

        // Fallback
        return new ErrorInfo(
                HttpStatus.INTERNAL_SERVER_ERROR,
                "An unexpected gateway error occurred",
                "INTERNAL_ERROR"
        );
    }

    private String buildErrorBody(ErrorInfo info, String path, String traceId) {
        String traceField = traceId != null
                ? String.format(",\"traceId\":\"%s\"", traceId)
                : "";
        return String.format(
                "{\"error\":\"%s\","
                + "\"message\":\"%s\","
                + "\"path\":\"%s\","
                + "\"code\":\"%s\""
                + "%s}",
                info.status.getReasonPhrase(),
                info.message,
                path,
                info.code,
                traceField
        );
    }

    // -------------------------------------------------------------------------
    // Inner types
    // -------------------------------------------------------------------------

    private record ErrorInfo(HttpStatus status, String message, String code) {}
}
