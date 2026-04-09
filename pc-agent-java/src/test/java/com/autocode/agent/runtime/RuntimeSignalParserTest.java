package com.autocode.agent.runtime;

import com.autocode.protocol.model.ServiceRuntimeDescriptor;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class RuntimeSignalParserTest {

    @Test
    void parsePortBindingsSupportsMixedTokenShapes() {
        List<ServiceRuntimeDescriptor.PortBinding> bindings = RuntimeSignalParser.parsePortBindings(
                "8080,http:8081:http,9090:grpc,grpc:9091:grpc,invalid,api:notaport");

        assertEquals(4, bindings.size());
        assertEquals("p1", bindings.get(0).getName());
        assertEquals(8080, bindings.get(0).getPort());
        assertEquals("http", bindings.get(0).getProtocol());

        assertEquals("http", bindings.get(1).getName());
        assertEquals(8081, bindings.get(1).getPort());
        assertEquals("http", bindings.get(1).getProtocol());

        assertEquals("p2", bindings.get(2).getName());
        assertEquals(9090, bindings.get(2).getPort());
        assertEquals("grpc", bindings.get(2).getProtocol());

        assertEquals("grpc", bindings.get(3).getName());
        assertEquals(9091, bindings.get(3).getPort());
        assertEquals("grpc", bindings.get(3).getProtocol());
    }

    @Test
    void resolvePrimaryRuntimePortPrefersSinglePortThenFallsBackToPortsList() {
        Integer primary = RuntimeSignalParser.resolvePrimaryRuntimePort(Map.of(
                "MVP_RUNTIME_PORT", "8443",
                "MVP_RUNTIME_PORTS", "http:8080:http"));
        assertEquals(8443, primary);

        Integer fallback = RuntimeSignalParser.resolvePrimaryRuntimePort(Map.of(
                "MVP_RUNTIME_PORT", "not-a-port",
                "MVP_RUNTIME_PORTS", "http:8081:http,grpc:9090:grpc"));
        assertEquals(8081, fallback);
    }

    @Test
    void normalizeHealthPathAddsSlashAndHandlesBlank() {
        assertEquals("/healthz", RuntimeSignalParser.normalizeHealthPath("healthz"));
        assertEquals("/ready", RuntimeSignalParser.normalizeHealthPath("/ready"));
        assertNull(RuntimeSignalParser.normalizeHealthPath("   "));
    }
}
