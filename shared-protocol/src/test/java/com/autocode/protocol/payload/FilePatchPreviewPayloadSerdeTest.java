package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FilePatchPreviewPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void file_patch_preview_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = FilePatchPreviewPayloadSerdeTest.class.getResourceAsStream("/examples/file_patch_preview.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/file_patch_preview.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            FilePatchPreviewPayload payload = MAPPER.treeToValue(payloadNode, FilePatchPreviewPayload.class);
            assertEquals("trc_task_test_123", payload.getTraceId());
            assertEquals("run_test_patch_001", payload.getRunId());
            assertEquals("unified", payload.getFormat());
            assertTrue(payload.getPatch().contains("diff --git"));
            assertNotNull(payload.getFiles());
            assertEquals(1, payload.getFiles().size());
            assertEquals("src/main.ts", payload.getFiles().get(0).getPath());
            assertEquals("modify", payload.getFiles().get(0).getChangeType());
            assertEquals("sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc", payload.getPreviewHash());
        }
    }
}
