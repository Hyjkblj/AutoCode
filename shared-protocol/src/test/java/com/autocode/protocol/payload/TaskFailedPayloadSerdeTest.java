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
            assertEquals("unsupported_target", payload.getReason());
            assertEquals("NL2WEB_UNSUPPORTED_TARGET", payload.getErrorCode());
            assertEquals("trc_task_test_123", payload.getTraceId());
            assertEquals("run_test_nl2web_001", payload.getRunId());
        }
    }
}

