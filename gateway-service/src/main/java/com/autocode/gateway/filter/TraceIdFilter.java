package com.autocode.gateway.filter;

import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.UUID;

/**
 * Global filter to ensure trace ID propagation across all requests.
 *
 * <p>Adds {@code X-Trace-Id} and {@code X-Request-Id} headers if not present
 * and propagates them to downstream services. Also forwards W3C
 * {@code traceparent} and B3 {@code X-B3-TraceId} headers when present so
 * that distributed tracing frameworks (OpenTelemetry, Zipkin) can correlate
 * spans across service boundaries.
 *
 * <p>Satisfies Requirement 9.3: trace IDs SHALL be propagated to downstream
 * services.
 */
@Component
public class TraceIdFilter implements GlobalFilter, Ordered {

    private static final String TRACE_ID_HEADER = "X-Trace-Id";
    private static final String REQUEST_ID_HEADER = "X-Request-Id";
    private static final String TRACEPARENT_HEADER = "traceparent";
    private static final String B3_TRACE_ID_HEADER = "X-B3-TraceId";
    private static final String B3_SPAN_ID_HEADER = "X-B3-SpanId";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();

        // Get or generate trace ID
        String traceId = request.getHeaders().getFirst(TRACE_ID_HEADER);
        if (traceId == null || traceId.trim().isEmpty()) {
            traceId = generateTraceId();
        }

        // Get or generate request ID
        String requestId = request.getHeaders().getFirst(REQUEST_ID_HEADER);
        if (requestId == null || requestId.trim().isEmpty()) {
            requestId = generateRequestId();
        }

        ServerHttpRequest.Builder mutatedRequest = request.mutate()
                .header(TRACE_ID_HEADER, traceId)
                .header(REQUEST_ID_HEADER, requestId);

        // Forward W3C traceparent if present (OpenTelemetry)
        String traceparent = request.getHeaders().getFirst(TRACEPARENT_HEADER);
        if (traceparent != null && !traceparent.isBlank()) {
            mutatedRequest.header(TRACEPARENT_HEADER, traceparent);
        }

        // Forward B3 trace headers if present (Zipkin / Brave)
        String b3TraceId = request.getHeaders().getFirst(B3_TRACE_ID_HEADER);
        if (b3TraceId != null && !b3TraceId.isBlank()) {
            mutatedRequest.header(B3_TRACE_ID_HEADER, b3TraceId);
        }
        String b3SpanId = request.getHeaders().getFirst(B3_SPAN_ID_HEADER);
        if (b3SpanId != null && !b3SpanId.isBlank()) {
            mutatedRequest.header(B3_SPAN_ID_HEADER, b3SpanId);
        }

        // Echo trace ID back in the response for client-side correlation
        exchange.getResponse().getHeaders().add(TRACE_ID_HEADER, traceId);
        exchange.getResponse().getHeaders().add(REQUEST_ID_HEADER, requestId);

        return chain.filter(exchange.mutate().request(mutatedRequest.build()).build());
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }

    private String generateTraceId() {
        return "trace-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }

    private String generateRequestId() {
        return "req-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
    }
}