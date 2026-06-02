package com.autocode.gateway.health;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.Status;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class GatewayHealthIndicatorTest {

    @Mock
    private WebClient webClient;

    @Mock
    private WebClient.RequestHeadersUriSpec requestHeadersUriSpec;

    @Mock
    private WebClient.RequestHeadersSpec requestHeadersSpec;

    @Mock
    private WebClient.ResponseSpec responseSpec;

    private GatewayHealthIndicator healthIndicator;

    @BeforeEach
    void setUp() {
        healthIndicator = new GatewayHealthIndicator();
        ReflectionTestUtils.setField(healthIndicator, "webClient", webClient);
        ReflectionTestUtils.setField(healthIndicator, "controlPlaneUrl", "http://localhost:8058");
        ReflectionTestUtils.setField(healthIndicator, "javaSandboxUrl", "http://localhost:18080");
    }

    @Test
    void health_WhenAllUpstreamServicesHealthy_ReturnsUp() {
        when(webClient.get()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri(anyString())).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);

        when(responseSpec.bodyToMono(String.class))
                .thenReturn(Mono.just("{\"status\":\"UP\"}"))
                .thenReturn(Mono.just("{\"ok\":true,\"status\":\"up\"}"));

        Health health = healthIndicator.health();

        assertEquals(Status.UP, health.getStatus());
        assertEquals(8080, health.getDetails().get("port"));
        assertTrue(health.getDetails().containsKey("upstreamServices"));
        assertTrue(health.getDetails().containsKey("routingConfigured"));
        assertTrue((Boolean) health.getDetails().get("routingConfigured"));

        @SuppressWarnings("unchecked")
        Map<String, Object> upstreamServices = (Map<String, Object>) health.getDetails().get("upstreamServices");
        assertTrue((Boolean) upstreamServices.get("controlPlaneHealthy"));
        assertTrue((Boolean) upstreamServices.get("javaSandboxHealthy"));
    }

    @Test
    void health_WhenControlPlaneDown_ReturnsDown() {
        when(webClient.get()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri(anyString())).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);

        when(responseSpec.bodyToMono(String.class))
                .thenReturn(Mono.error(new RuntimeException("Connection refused")))
                .thenReturn(Mono.just("{\"ok\":true,\"status\":\"up\"}"));

        Health health = healthIndicator.health();

        assertEquals(Status.DOWN, health.getStatus());

        @SuppressWarnings("unchecked")
        Map<String, Object> upstreamServices = (Map<String, Object>) health.getDetails().get("upstreamServices");
        assertFalse((Boolean) upstreamServices.get("controlPlaneHealthy"));
        assertTrue((Boolean) upstreamServices.get("javaSandboxHealthy"));
        assertTrue(upstreamServices.containsKey("controlPlaneError"));
    }

    @Test
    void health_WhenJavaSandboxDown_ReturnsDown() {
        when(webClient.get()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri(anyString())).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);

        when(responseSpec.bodyToMono(String.class))
                .thenReturn(Mono.just("{\"status\":\"UP\"}"))
                .thenReturn(Mono.error(new RuntimeException("Connection refused")));

        Health health = healthIndicator.health();

        assertEquals(Status.DOWN, health.getStatus());

        @SuppressWarnings("unchecked")
        Map<String, Object> upstreamServices = (Map<String, Object>) health.getDetails().get("upstreamServices");
        assertTrue((Boolean) upstreamServices.get("controlPlaneHealthy"));
        assertFalse((Boolean) upstreamServices.get("javaSandboxHealthy"));
        assertTrue(upstreamServices.containsKey("javaSandboxError"));
    }

    @Test
    void health_IncludesExpectedFeatures() {
        when(webClient.get()).thenReturn(requestHeadersUriSpec);
        when(requestHeadersUriSpec.uri(anyString())).thenReturn(requestHeadersSpec);
        when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);

        when(responseSpec.bodyToMono(String.class))
                .thenReturn(Mono.just("{\"status\":\"UP\"}"))
                .thenReturn(Mono.just("{\"ok\":true,\"status\":\"up\"}"));

        Health health = healthIndicator.health();

        assertTrue(health.getDetails().containsKey("features"));

        @SuppressWarnings("unchecked")
        Map<String, Object> features = (Map<String, Object>) health.getDetails().get("features");
        assertTrue((Boolean) features.get("traceIdPropagation"));
        assertTrue((Boolean) features.get("authHeaderPropagation"));
        assertTrue((Boolean) features.get("timeoutPolicies"));
        assertTrue((Boolean) features.get("rateLimiting"));
    }
}
