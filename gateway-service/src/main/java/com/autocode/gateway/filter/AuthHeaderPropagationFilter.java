package com.autocode.gateway.filter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpHeaders;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.List;

/**
 * Global filter that propagates authentication headers to downstream services.
 *
 * <p>Forwards the following headers when present:
 * <ul>
 *   <li>{@code Authorization} – Bearer token or API key</li>
 *   <li>{@code X-Auth-User} – Authenticated user identity</li>
 *   <li>{@code X-Auth-Roles} – Comma-separated role list</li>
 *   <li>{@code X-Tenant-Id} – Multi-tenant identifier</li>
 * </ul>
 *
 * <p>Satisfies Requirement 9.3: trace IDs and authentication headers SHALL be
 * propagated to downstream services.
 */
@Component
public class AuthHeaderPropagationFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(AuthHeaderPropagationFilter.class);

    /** Headers that must be forwarded verbatim to every downstream service. */
    private static final List<String> AUTH_HEADERS = List.of(
            HttpHeaders.AUTHORIZATION,
            "X-Auth-User",
            "X-Auth-Roles",
            "X-Tenant-Id"
    );

    /**
     * Run just after {@link TraceIdFilter} (order 1) so trace IDs are already
     * present when auth headers are logged.
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 1;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        HttpHeaders incomingHeaders = request.getHeaders();

        ServerHttpRequest.Builder mutatedRequest = request.mutate();
        boolean anyPropagated = false;

        for (String header : AUTH_HEADERS) {
            String value = incomingHeaders.getFirst(header);
            if (value != null && !value.isBlank()) {
                mutatedRequest.header(header, value);
                anyPropagated = true;
                if (log.isDebugEnabled()) {
                    // Never log the actual Authorization value – only its presence.
                    String logValue = HttpHeaders.AUTHORIZATION.equalsIgnoreCase(header)
                            ? "<redacted>"
                            : value;
                    log.debug("Propagating auth header '{}': {}", header, logValue);
                }
            }
        }

        if (!anyPropagated) {
            log.debug("No authentication headers found on incoming request – forwarding unauthenticated");
        }

        return chain.filter(exchange.mutate().request(mutatedRequest.build()).build());
    }
}
