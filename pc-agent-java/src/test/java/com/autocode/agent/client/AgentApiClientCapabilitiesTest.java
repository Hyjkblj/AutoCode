package com.autocode.agent.client;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentApiClientCapabilitiesTest {

    @Test
    void buildCapabilitiesReturnsBaseCapabilitiesWithoutRuntimeSignals() {
        String capabilities = AgentApiClient.buildCapabilities("coder", Map.of());
        assertEquals("codex,events,approval,profile:coder", capabilities);
    }

    @Test
    void buildCapabilitiesIncludesRuntimeHealthMarkersWhenSignalsPresent() {
        String capabilities = AgentApiClient.buildCapabilities("web", Map.of(
                "MVP_RUNTIME_SERVICE_ID", "control-plane-api",
                "MVP_RUNTIME_PORT", "8080",
                "MVP_RUNTIME_HEALTH_PATH", "actuator/health"
        ));
        assertTrue(capabilities.contains("runtime.descriptor.v1"));
        assertTrue(capabilities.contains("runtime.service:control-plane-api"));
        assertTrue(capabilities.contains("runtime.port:8080"));
        assertTrue(capabilities.contains("runtime.health.path:/actuator/health"));
    }

    @Test
    void buildCapabilitiesReadsPrimaryPortFromRuntimePortsList() {
        String capabilities = AgentApiClient.buildCapabilities("coder", Map.of(
                "MVP_RUNTIME_PORTS", "http:8081:http,grpc:9090:grpc"
        ));
        assertTrue(capabilities.contains("runtime.descriptor.v1"));
        assertTrue(capabilities.contains("runtime.port:8081"));
        assertTrue(capabilities.contains("runtime.ports.count:2"));
    }

    @Test
    void buildCapabilitiesFallsBackToRuntimePortsWhenSinglePortInvalid() {
        String capabilities = AgentApiClient.buildCapabilities("coder", Map.of(
                "MVP_RUNTIME_PORT", "abc",
                "MVP_RUNTIME_PORTS", "http:8081:http,grpc:9090:grpc"
        ));
        assertTrue(capabilities.contains("runtime.descriptor.v1"));
        assertTrue(capabilities.contains("runtime.port:8081"));
        assertTrue(capabilities.contains("runtime.ports.count:2"));
        assertFalse(capabilities.contains("runtime.port:abc"));
    }
}

