package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class TaskFailedPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void task_failed_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = TaskFailedPayloadSerdeTest.class.getResourceAsStream("/examples/task_failed.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/task_failed.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            TaskFailedPayload payload = MAPPER.treeToValue(payloadNode, TaskFailedPayload.class);
            assertEquals("fix_loop_exhausted", payload.getReason());
            assertEquals("FIX_LOOP_EXHAUSTED", payload.getErrorCode());
            assertEquals("code_change_pipeline", payload.getPlanName());
            assertEquals("failed", payload.getStatus());
            assertEquals("trc_task_test_123", payload.getTraceId());
            assertEquals("run_test_001", payload.getRunId());
        }
    }

    @Test
    void task_failed_payload_exposes_nl2web_reason_constants() {
        assertEquals("unsupported_target", TaskFailedPayload.REASON_UNSUPPORTED_TARGET);
        assertEquals("template_generation_failed", TaskFailedPayload.REASON_TEMPLATE_GENERATION_FAILED);
        assertEquals("artifact_pack_failed", TaskFailedPayload.REASON_ARTIFACT_PACK_FAILED);
        assertEquals("artifact_publish_failed", TaskFailedPayload.REASON_ARTIFACT_PUBLISH_FAILED);
        assertEquals("event_publish_failed", TaskFailedPayload.REASON_EVENT_PUBLISH_FAILED);
    }
}

