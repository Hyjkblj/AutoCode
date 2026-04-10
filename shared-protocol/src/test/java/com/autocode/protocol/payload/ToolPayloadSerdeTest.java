package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class ToolPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void tool_start_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = ToolPayloadSerdeTest.class.getResourceAsStream("/examples/tool_start.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/tool_start.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            ToolStartPayload payload = MAPPER.treeToValue(payloadNode, ToolStartPayload.class);
            assertEquals("command.exec", payload.getTool());
            assertEquals("run_command", payload.getAction());
            assertEquals("D:/workspace/test", payload.getWorkspaceRef());
            assertEquals("run_test_001", payload.getRunId());
            assertEquals("skill.code.author", payload.getIntentSkill());
            assertEquals("rule_based", payload.getIntentRoute());
        }
    }

    @Test
    void tool_end_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = ToolPayloadSerdeTest.class.getResourceAsStream("/examples/tool_end.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/tool_end.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            ToolEndPayload payload = MAPPER.treeToValue(payloadNode, ToolEndPayload.class);
            assertEquals("command.exec", payload.getTool());
            assertEquals("ok", payload.getStatus());
            assertEquals(0, payload.getExitCode());
        }
    }
}
