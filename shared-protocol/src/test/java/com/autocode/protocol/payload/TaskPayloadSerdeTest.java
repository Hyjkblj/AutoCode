package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TaskPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void task_done_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = TaskPayloadSerdeTest.class.getResourceAsStream("/examples/task_done.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/task_done.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            TaskDonePayload payload = MAPPER.treeToValue(payloadNode, TaskDonePayload.class);
            assertEquals("coded_reviewed_tested", payload.getResult());
            assertEquals("code_change", payload.getIntent());
            assertEquals("code_change_pipeline", payload.getPlanName());
            assertEquals(3, payload.getSteps().size());
            assertTrue(Boolean.TRUE.equals(payload.getReviewApproved()));
            assertEquals("ok", payload.getTestStatus());
            assertEquals(2, payload.getTestAttempts());
            assertEquals(1, payload.getTestRetries());
            assertEquals(1, payload.getAttempt());
            assertEquals(3, payload.getMaxAttempts());
        }
    }

    @Test
    void task_failed_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = TaskPayloadSerdeTest.class.getResourceAsStream("/examples/task_failed.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/task_failed.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            TaskFailedPayload payload = MAPPER.treeToValue(payloadNode, TaskFailedPayload.class);
            assertEquals("fix_loop_exhausted", payload.getReason());
            assertEquals("code_change_pipeline", payload.getPlanName());
            assertEquals("failed", payload.getStatus());
            assertEquals("FIX_LOOP_EXHAUSTED", payload.getErrorCode());
            assertTrue(Boolean.FALSE.equals(payload.getRetryable()));
            assertEquals(3, payload.getAttempt());
            assertEquals(3, payload.getMaxAttempts());
            assertEquals("high", payload.getRiskLevel());
            assertEquals(2, payload.getIssues().size());
        }
    }
}
