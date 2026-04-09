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

    @Test
    void deserializes_nl2web_alias_metadata_shape() throws Exception {
        try (InputStream in = ArtifactReadyPayloadSerdeTest.class.getResourceAsStream("/examples/artifact_ready_nl2web.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/artifact_ready_nl2web.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            ArtifactReadyPayload p = MAPPER.treeToValue(payloadNode, ArtifactReadyPayload.class);
            assertEquals("web", p.getTarget());
            assertEquals("web-basic", p.getTemplateId());
            assertEquals("zip", p.getExportMode());
            assertNotNull(p.getArtifact());
            assertEquals("art_export_zip_test_001", p.getArtifact().getArtifactId());
            assertEquals("export.zip", p.getArtifact().getFileName());
            assertEquals("sha256:1b2c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef", p.getArtifact().getSha256());
            assertEquals("application/zip", p.getArtifact().getMimeType());
            assertEquals("zip", p.getKind());
        }
    }
}
