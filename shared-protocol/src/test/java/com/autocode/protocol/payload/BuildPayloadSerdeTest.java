package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class BuildPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void build_started_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = BuildPayloadSerdeTest.class.getResourceAsStream("/examples/build_started.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/build_started.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            BuildStartedPayload payload = MAPPER.treeToValue(payloadNode, BuildStartedPayload.class);
            assertEquals("build_test_001", payload.getBuildId());
            assertEquals("build.run", payload.getTool());
            assertEquals("web", payload.getTarget());
        }
    }

    @Test
    void build_log_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = BuildPayloadSerdeTest.class.getResourceAsStream("/examples/build_log.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/build_log.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            BuildLogPayload payload = MAPPER.treeToValue(payloadNode, BuildLogPayload.class);
            assertEquals("build_test_001", payload.getBuildId());
            assertEquals("info", payload.getLevel());
            assertEquals("vite build", payload.getMessage());
        }
    }

    @Test
    void build_done_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = BuildPayloadSerdeTest.class.getResourceAsStream("/examples/build_done.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/build_done.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            BuildDonePayload payload = MAPPER.treeToValue(payloadNode, BuildDonePayload.class);
            assertEquals("build_test_001", payload.getBuildId());
            assertEquals("success", payload.getStatus());
            assertEquals(9000L, payload.getDurationMs());
            assertNotNull(payload.getReportArtifact());
            assertEquals("art_build_report_test_001", payload.getReportArtifact().getArtifactId());
        }
    }
}
