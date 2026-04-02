package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * M1: {@link ArtifactReadyPayload} matches {@code artifact_ready.v1.example.json} payload shape
 * (same file name under {@code src/main/resources/examples} and test resources).
 */
class ArtifactReadyPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void deserializes_payload_from_example_file_shape() throws Exception {
        try (InputStream in = ArtifactReadyPayloadSerdeTest.class.getResourceAsStream("/examples/artifact_ready.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/artifact_ready.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            ArtifactReadyPayload p = MAPPER.treeToValue(payloadNode, ArtifactReadyPayload.class);
            assertNotNull(p.getArtifact());
            assertEquals("art_zip_7f3c2a", p.getArtifact().getArtifactId());
            assertEquals("zip", p.getArtifact().getType());
            assertEquals("zip", p.getKind());
            assertEquals("npm ci && npm run build", p.getArtifact().getBuild().getCommand());
        }
    }
}
