package com.autocode.gateway.filter;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.http.HttpStatus;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.net.ConnectException;
import java.util.concurrent.TimeoutException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.core.Ordered.LOWEST_PRECEDENCE;

class ErrorHandlingFilterTest {

    private ErrorHandlingFilter filter;
    private GatewayFilterChain chain;

    @BeforeEach
    void setUp() {
        filter = new ErrorHandlingFilter();
        chain = mock(GatewayFilterChain.class);
    }

    @Test
    void order_isLowestPrecedenceMinusTen() {
        assertThat(filter.getOrder()).isEqualTo(LOWEST_PRECEDENCE - 10);
    }

    // -------------------------------------------------------------------------
    // Happy path
    // -------------------------------------------------------------------------

    @Test
    void filter_successfulChain_completesNormally() {
        when(chain.filter(any())).thenReturn(Mono.empty());

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();
    }

    // -------------------------------------------------------------------------
    // Connection refused → 503
    // -------------------------------------------------------------------------

    @Test
    void filter_connectException_returns503() {
        when(chain.filter(any())).thenReturn(Mono.error(new ConnectException("Connection refused")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
    }

    @Test
    void filter_connectExceptionWrapped_returns503() {
        RuntimeException wrapped = new RuntimeException("upstream error",
                new ConnectException("Connection refused"));
        when(chain.filter(any())).thenReturn(Mono.error(wrapped));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
    }

    // -------------------------------------------------------------------------
    // Timeout → 504
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

    // -------------------------------------------------------------------------
    // ResponseStatusException → mapped status
    // -------------------------------------------------------------------------

    @Test
    void filter_responseStatusException_returnsMappedStatus() {
        when(chain.filter(any())).thenReturn(
                Mono.error(new ResponseStatusException(HttpStatus.BAD_REQUEST, "bad input")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    // -------------------------------------------------------------------------
    // Unknown exception → 500
    // -------------------------------------------------------------------------

    @Test
    void filter_unknownException_returns500() {
        when(chain.filter(any())).thenReturn(Mono.error(new RuntimeException("unexpected")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.INTERNAL_SERVER_ERROR);
    }

    // -------------------------------------------------------------------------
    // Trace ID included in error body
    // -------------------------------------------------------------------------

    @Test
    void filter_errorWithTraceId_responseBodyContainsTraceId() {
        when(chain.filter(any())).thenReturn(Mono.error(new ConnectException("Connection refused")));

        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header("X-Trace-Id", "trace-xyz789")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
    }
}
