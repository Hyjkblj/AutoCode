package com.autocode.gateway.config;

import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

/**
 * Configuration for Spring Cloud Gateway's built-in {@code RequestRateLimiter}
 * filter.
 *
 * <p>The {@code clientIpKeyResolver} bean is referenced in {@code application.yml}
 * via the SpEL expression {@code #{@clientIpKeyResolver}} and is used to derive
 * the rate-limit bucket key from the client's IP address.
 *
 * <p>Satisfies Requirement 9.5: rate limiting of 100 requests per minute per
 * client.
 */
@Configuration
public class RateLimitConfig {

    /**
     * Resolves the rate-limit key from the client IP address.
     *
     * <p>Prefers {@code X-Forwarded-For} (set by upstream load balancers) over
     * the raw remote address so that clients behind a proxy are correctly
     * bucketed.
     */
    @Bean
    public KeyResolver clientIpKeyResolver() {
        return exchange -> {
            String forwarded = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
            if (forwarded != null && !forwarded.isBlank()) {
                // X-Forwarded-For may be a comma-separated list; use the first entry
                return Mono.just(forwarded.split(",")[0].trim());
            }
            if (exchange.getRequest().getRemoteAddress() != null) {
                return Mono.just(
                        exchange.getRequest().getRemoteAddress().getAddress().getHostAddress()
                );
            }
            return Mono.just("unknown");
        };
    }
}
