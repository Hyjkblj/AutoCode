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
            assertEquals("exec_failed", payload.getReason());
            assertEquals("Command exited with non-zero status", payload.getDetail());
            assertEquals("COMMAND_EXIT_NON_ZERO", payload.getErrorCode());
        }
    }
}
