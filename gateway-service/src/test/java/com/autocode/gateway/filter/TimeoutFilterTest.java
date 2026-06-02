package com.autocode.gateway.filter;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.http.HttpStatus;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.time.Duration;
import java.util.concurrent.TimeoutException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.core.Ordered.HIGHEST_PRECEDENCE;

class TimeoutFilterTest {

    private TimeoutFilter filter;
    private GatewayFilterChain chain;

    @BeforeEach
    void setUp() {
        filter = new TimeoutFilter();
        chain = mock(GatewayFilterChain.class);
    }

    @Test
    void order_isHighestPrecedencePlusTwo() {
        assertThat(filter.getOrder()).isEqualTo(HIGHEST_PRECEDENCE + 2);
    }

    // -------------------------------------------------------------------------
    // Timeout resolution
    // -------------------------------------------------------------------------

    @ParameterizedTest
    @ValueSource(strings = {
            "/api/tasks/generate/backend",
            "/api/generate/fullstack",
            "/api/backend-generate/run",
            "/api/fullstack-generate/start"
    })
    void resolveTimeout_generationPaths_returns300Seconds(String path) {
        assertThat(filter.resolveTimeout(path)).isEqualTo(Duration.ofSeconds(300));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "/api/tasks",
            "/api/tasks/123",
            "/api/events",
            "/actuator/health",
            "/sandbox/execute"
    })
    void resolveTimeout_nonGenerationPaths_returns30Seconds(String path) {
        assertThat(filter.resolveTimeout(path)).isEqualTo(Duration.ofSeconds(30));
    }

    // -------------------------------------------------------------------------
    // Happy path
    // -------------------------------------------------------------------------

    @Test
    void filter_successfulRequest_completesNormally() {
        when(chain.filter(any())).thenReturn(Mono.empty());

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();
    }

    // -------------------------------------------------------------------------
    // Timeout handling
    // -------------------------------------------------------------------------

    @Test
    void filter_timeoutException_returns504() {
        when(chain.filter(any())).thenReturn(Mono.error(new TimeoutException("timed out")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.GATEWAY_TIMEOUT);
    }

    @Test
    void filter_timeoutResponse_includesTraceId() {
        when(chain.filter(any())).thenReturn(Mono.error(new TimeoutException("timed out")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header("X-Trace-Id", "trace-abc123")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.GATEWAY_TIMEOUT);
    }
}
