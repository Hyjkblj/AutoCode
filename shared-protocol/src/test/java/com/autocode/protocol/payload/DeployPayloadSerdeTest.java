package com.autocode.protocol.payload;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class DeployPayloadSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    @Test
    void deploy_plan_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = DeployPayloadSerdeTest.class.getResourceAsStream("/examples/deploy_plan.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/deploy_plan.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            DeployPlanPayload p = MAPPER.treeToValue(payloadNode, DeployPlanPayload.class);
            assertEquals("deploy_req_test_001", p.getRequestId());
            assertEquals("staging", p.getEnvironment());
            assertNotNull(p.getArtifact());
            assertEquals("art_zip_test_001", p.getArtifact().getArtifactId());
            assertNotNull(p.getContext());
            assertEquals("app.publish", p.getContext().getAction());
        }
    }

    @Test
    void deploy_result_payload_deserializes_from_example_shape() throws Exception {
        try (InputStream in = DeployPayloadSerdeTest.class.getResourceAsStream("/examples/deploy_result.v1.example.json")) {
            assertNotNull(in, "Missing test resource /examples/deploy_result.v1.example.json");
            JsonNode root = MAPPER.readTree(in);
            JsonNode payloadNode = root.get("payload");
            assertNotNull(payloadNode);
            DeployResultPayload p = MAPPER.treeToValue(payloadNode, DeployResultPayload.class);
            assertEquals("deploy_req_test_001", p.getRequestId());
            assertEquals("success", p.getStatus());
            assertEquals("dep_test_001", p.getDeploymentId());
            assertNotNull(p.getResultArtifact());
            assertEquals("deploy_report", p.getResultArtifact().getType());
        }
    }
}
