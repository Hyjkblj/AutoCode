package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class LifecyclePayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void task_created_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = LifecyclePayloadSerdeTest.class.getResourceAsStream("/examples/task_created.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/task_created.v1.example.json");
            JsonNode payloadNode = MAPPER.readTree(in).get("payload");
            assertNotNull(payloadNode);
            TaskCreatedPayload payload = MAPPER.treeToValue(payloadNode, TaskCreatedPayload.class);
            assertEquals("proj_test_001", payload.getProjectId());
            assertEquals("default", payload.getRiskPolicy());
        }
    }

    @Test
    void task_started_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = LifecyclePayloadSerdeTest.class.getResourceAsStream("/examples/task_started.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/task_started.v1.example.json");
            JsonNode payloadNode = MAPPER.readTree(in).get("payload");
            assertNotNull(payloadNode);
            TaskStartedPayload payload = MAPPER.treeToValue(payloadNode, TaskStartedPayload.class);
            assertEquals("node-test-1", payload.getNodeId());
        }
    }

    @Test
    void assistant_output_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = LifecyclePayloadSerdeTest.class.getResourceAsStream("/examples/assistant_output.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/assistant_output.v1.example.json");
            JsonNode payloadNode = MAPPER.readTree(in).get("payload");
            assertNotNull(payloadNode);
            AssistantOutputPayload payload = MAPPER.treeToValue(payloadNode, AssistantOutputPayload.class);
            assertEquals("Reviewer finished: medium risk with two issues, entering fix loop attempt 1/3.", payload.getMessage());
            assertEquals("ReviewerAgent", payload.getStage());
            assertEquals("code_change", payload.getIntent());
            assertEquals("medium", payload.getRiskLevel());
            assertEquals(1, payload.getAttempt());
            assertEquals(3, payload.getMaxAttempts());
        }
    }

    @Test
    void heartbeat_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = LifecyclePayloadSerdeTest.class.getResourceAsStream("/examples/heartbeat.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/heartbeat.v1.example.json");
            JsonNode payloadNode = MAPPER.readTree(in).get("payload");
            assertNotNull(payloadNode);
            HeartbeatPayload payload = MAPPER.treeToValue(payloadNode, HeartbeatPayload.class);
            assertEquals("node-test-1", payload.getNodeId());
            assertEquals("alive", payload.getStatus());
            assertEquals(30000L, payload.getUptimeMs());
        }
    }
}
