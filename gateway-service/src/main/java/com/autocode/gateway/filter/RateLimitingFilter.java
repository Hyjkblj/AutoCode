package com.autocode.gateway.filter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;

/**
 * Global filter implementing a sliding-window rate limiter backed by Redis.
 *
 * <p>Policy (Requirement 9.5): 100 requests per minute per client IP.
 *
 * <p>The client key is derived from the {@code X-Forwarded-For} header when
 * present, falling back to the remote address. Each key maps to a Redis counter
 * with a 60-second TTL. When the counter exceeds the limit the filter returns
 * HTTP 429 Too Many Requests with a {@code Retry-After} header.
 *
 * <p>If Redis is unavailable the filter fails open (allows the request) and
 * logs a warning, so a Redis outage does not take down the gateway.
 */
@Component
public class RateLimitingFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(RateLimitingFilter.class);

    /** Maximum requests allowed per client per window. */
    static final long MAX_REQUESTS_PER_WINDOW = 100;

    /** Length of the rate-limit window. */
    static final Duration WINDOW_DURATION = Duration.ofMinutes(1);

    private static final String RATE_LIMIT_KEY_PREFIX = "gateway:ratelimit:";

    private final ReactiveStringRedisTemplate redisTemplate;

    public RateLimitingFilter(ReactiveStringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 3;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String clientKey = resolveClientKey(exchange);
        String redisKey = RATE_LIMIT_KEY_PREFIX + clientKey;

        return redisTemplate.opsForValue()
                .increment(redisKey)
                .flatMap(count -> {
                    if (count == 1) {
                        // First request in this window – set the TTL
                        return redisTemplate.expire(redisKey, WINDOW_DURATION)
                                .thenReturn(count);
                    }
                    return Mono.just(count);
                })
                .flatMap(count -> {
                    // Add rate-limit headers to every response
                    long remaining = Math.max(0, MAX_REQUESTS_PER_WINDOW - count);
                    exchange.getResponse().getHeaders()
                            .add("X-RateLimit-Limit", String.valueOf(MAX_REQUESTS_PER_WINDOW));
                    exchange.getResponse().getHeaders()
                            .add("X-RateLimit-Remaining", String.valueOf(remaining));
                    exchange.getResponse().getHeaders()
                            .add("X-RateLimit-Window", WINDOW_DURATION.getSeconds() + "s");

                    if (count > MAX_REQUESTS_PER_WINDOW) {
                        log.warn("Rate limit exceeded for client '{}': {} requests in window", clientKey, count);
                        return handleRateLimitExceeded(exchange, clientKey);
                    }

                    return chain.filter(exchange);
                })
                .onErrorResume(ex -> {
                    // Fail open: if Redis is unavailable, allow the request
                    log.warn("Redis unavailable for rate limiting (client: {}), failing open: {}", clientKey, ex.getMessage());
                    return chain.filter(exchange);
                });
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Derives a stable client identifier from the request.
     * Prefers {@code X-Forwarded-For} (set by load balancers) over the raw
     * remote address so that clients behind a proxy are correctly identified.
     */
    String resolveClientKey(ServerWebExchange exchange) {
        String forwarded = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            // X-Forwarded-For may be a comma-separated list; take the first entry
            return forwarded.split(",")[0].trim();
        }
        if (exchange.getRequest().getRemoteAddress() != null) {
            return exchange.getRequest().getRemoteAddress().getAddress().getHostAddress();
        }
        return "unknown";
    }

    private Mono<Void> handleRateLimitExceeded(ServerWebExchange exchange, String clientKey) {
        String traceId = exchange.getRequest().getHeaders().getFirst("X-Trace-Id");
        long retryAfter = WINDOW_DURATION.getSeconds();

        exchange.getResponse().setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        exchange.getResponse().getHeaders().add("Retry-After", String.valueOf(retryAfter));

        String traceField = traceId != null
                ? String.format(",\"traceId\":\"%s\"", traceId)
                : "";
        String body = String.format(
                "{\"error\":\"Too Many Requests\","
                + "\"message\":\"Rate limit of %d requests per minute exceeded\","
                + "\"retryAfterSeconds\":%d"
                + "%s}",
                MAX_REQUESTS_PER_WINDOW, retryAfter, traceField
        );

        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        return exchange.getResponse().writeWith(
                Mono.just(exchange.getResponse().bufferFactory().wrap(bytes))
        );
    }
}
