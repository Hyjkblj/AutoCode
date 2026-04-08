package com.autocode.protocol.payload;

import com.autocode.protocol.model.ApprovalDecision;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class ApprovalPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void approval_required_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = ApprovalPayloadSerdeTest.class.getResourceAsStream("/examples/approval_required.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/approval_required.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            ApprovalRequiredPayload payload = MAPPER.treeToValue(payloadNode, ApprovalRequiredPayload.class);
            assertEquals("apr_test_001", payload.getApprovalId());
            assertEquals("app.publish", payload.getContext().getAction());
            assertEquals("publish.run", payload.getContext().getTool());
        }
    }

    @Test
    void approval_result_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = ApprovalPayloadSerdeTest.class.getResourceAsStream("/examples/approval_result.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/approval_result.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            ApprovalResultPayload payload = MAPPER.treeToValue(payloadNode, ApprovalResultPayload.class);
            assertEquals("apr_test_001", payload.getApprovalId());
            assertEquals(ApprovalDecision.REJECT, payload.getDecision());
            assertEquals(950L, payload.getWaitMs());
            assertEquals("blocked by reviewer", payload.getMessage());
        }
    }
}
