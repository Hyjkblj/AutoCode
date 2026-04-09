package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class SpecProposedPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void spec_proposed_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = SpecProposedPayloadSerdeTest.class.getResourceAsStream("/examples/spec_proposed.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/spec_proposed.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            SpecProposedPayload payload = MAPPER.treeToValue(payloadNode, SpecProposedPayload.class);
            assertEquals("web", payload.getTarget());
            assertEquals("web-basic", payload.getTemplateId());
            assertEquals("zip", payload.getExportMode());
            assertNotNull(payload.getArtifact());
            assertEquals("art_spec_test_001", payload.getArtifact().getArtifactId());
            assertEquals("spec", payload.getArtifact().getType());
            assertEquals("spec.json", payload.getPath());
            assertEquals("v1", payload.getSchemaVersion());
        }
    }
}
