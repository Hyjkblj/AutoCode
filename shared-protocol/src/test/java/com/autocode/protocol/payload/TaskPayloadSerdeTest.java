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
            assertEquals("executed", payload.getResult());
            assertEquals("command.exec", payload.getTool());
            assertEquals(0, payload.getExitCode());
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
            assertEquals("sandbox_request_failed", payload.getReason());
            assertEquals("error", payload.getStatus());
            assertTrue(Boolean.TRUE.equals(payload.getRetryable()));
        }
    }
}
