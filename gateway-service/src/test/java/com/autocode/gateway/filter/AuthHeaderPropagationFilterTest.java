package com.autocode.gateway.filter;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.core.Ordered.HIGHEST_PRECEDENCE;

class AuthHeaderPropagationFilterTest {

    private AuthHeaderPropagationFilter filter;
    private GatewayFilterChain chain;

    @BeforeEach
    void setUp() {
        filter = new AuthHeaderPropagationFilter();
        chain = mock(GatewayFilterChain.class);
        when(chain.filter(any())).thenReturn(Mono.empty());
    }

    @Test
    void order_isHighestPrecedencePlusOne() {
        assertThat(filter.getOrder()).isEqualTo(HIGHEST_PRECEDENCE + 1);
    }

    @Test
    void filter_propagatesAuthorizationHeader() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header(HttpHeaders.AUTHORIZATION, "Bearer token123")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(argThat(ex -> {
            String auth = ex.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
            return "Bearer token123".equals(auth);
        }));
    }

    @Test
    void filter_propagatesXAuthUserHeader() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header("X-Auth-User", "alice")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(argThat(ex ->
                "alice".equals(ex.getRequest().getHeaders().getFirst("X-Auth-User"))
        ));
    }

    @Test
    void filter_propagatesXAuthRolesHeader() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header("X-Auth-Roles", "ADMIN,USER")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(argThat(ex ->
                "ADMIN,USER".equals(ex.getRequest().getHeaders().getFirst("X-Auth-Roles"))
        ));
    }

    @Test
    void filter_propagatesXTenantIdHeader() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header("X-Tenant-Id", "tenant-42")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(argThat(ex ->
                "tenant-42".equals(ex.getRequest().getHeaders().getFirst("X-Tenant-Id"))
        ));
    }

    @Test
    void filter_propagatesMultipleAuthHeaders() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks")
                .header(HttpHeaders.AUTHORIZATION, "Bearer abc")
                .header("X-Auth-User", "bob")
                .header("X-Tenant-Id", "tenant-1")
                .build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(argThat(ex -> {
            HttpHeaders headers = ex.getRequest().getHeaders();
            return "Bearer abc".equals(headers.getFirst(HttpHeaders.AUTHORIZATION))
                    && "bob".equals(headers.getFirst("X-Auth-User"))
                    && "tenant-1".equals(headers.getFirst("X-Tenant-Id"));
        }));
    }

    @Test
    void filter_allowsRequestWithNoAuthHeaders() {
        MockServerHttpRequest request = MockServerHttpRequest.get("/api/tasks").build();
        MockServerWebExchange exchange = MockServerWebExchange.from(request);

        StepVerifier.create(filter.filter(exchange, chain))
                .verifyComplete();

        verify(chain).filter(any());
    }
}
