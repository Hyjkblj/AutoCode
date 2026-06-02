package com.autocode.gateway.filter;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.data.redis.core.ReactiveValueOperations;
import org.springframework.http.HttpStatus;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.net.InetSocketAddress;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.core.Ordered.HIGHEST_PRECEDENCE;

class RateLimitingFilterTest {

    private RateLimitingFilter filter;
    private GatewayFilterChain chain;
    private ReactiveStringRedisTemplate redisTemplate;
    private ReactiveValueOperations<String, String> valueOps;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        redisTemplate = mock(ReactiveStringRedisTemplate.class);
        valueOps = mock(ReactiveValueOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(redisTemplate.expire(anyString(), any())).thenReturn(Mono.just(true));

        filter = new RateLimitingFilter(redisTemplate);
        chain = mock(GatewayFilterChain.class);
        when(chain.filter(any())).thenReturn(Mono.empty());
    }

    @Test
    void order_isHighestPrecedencePlusThree() {
        assertThat(filter.getOrder()).isEqualTo(HIGHEST_PRECEDENCE + 3);
    }

    // -------------------------------------------------------------------------
    // Client key resolution
    // -------------------------------------------------------------------------

    @Test
    void resolveClientKey_usesXForwardedFor_whenPresent() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header("X-Forwarded-For", "10.0.0.1, 192.168.1.1")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        assertThat(filter.resolveClientKey(exchange)).isEqualTo("10.0.0.1");
    }

    @Test
    void resolveClientKey_fallsBackToRemoteAddress_whenNoForwardedFor() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .remoteAddress(new InetSocketAddress("192.168.0.5", 12345))
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        assertThat(filter.resolveClientKey(exchange)).isEqualTo("192.168.0.5");
    }

    // -------------------------------------------------------------------------
    // Under limit
    // -------------------------------------------------------------------------

    @Test
    void filter_underLimit_allowsRequest() {
        when(valueOps.increment(anyString())).thenReturn(Mono.just(50L));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(any());
        assertThat(exchange.getResponse().getHeaders().getFirst("X-RateLimit-Limit"))
                .isEqualTo("100");
        assertThat(exchange.getResponse().getHeaders().getFirst("X-RateLimit-Remaining"))
                .isEqualTo("50");
    }

    @Test
    void filter_firstRequest_setsTtlOnRedisKey() {
        when(valueOps.increment(anyString())).thenReturn(Mono.just(1L));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(redisTemplate).expire(anyString(), eq(RateLimitingFilter.WINDOW_DURATION));
    }

    // -------------------------------------------------------------------------
    // Over limit
    // -------------------------------------------------------------------------

    @Test
    void filter_overLimit_returns429() {
        when(valueOps.increment(anyString())).thenReturn(Mono.just(101L));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain, never()).filter(any());
        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
        assertThat(exchange.getResponse().getHeaders().getFirst("Retry-After")).isNotNull();
    }

    @Test
    void filter_overLimit_remainingHeaderIsZero() {
        when(valueOps.increment(anyString())).thenReturn(Mono.just(200L));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getHeaders().getFirst("X-RateLimit-Remaining"))
                .isEqualTo("0");
    }

    // -------------------------------------------------------------------------
    // Redis failure – fail open
    // -------------------------------------------------------------------------

    @Test
    void filter_redisUnavailable_failsOpenAndAllowsRequest() {
        when(valueOps.increment(anyString()))
                .thenReturn(Mono.error(new RuntimeException("Redis connection refused")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        // Request must be allowed through even when Redis is down
        verify(chain).filter(any());
    }
}
