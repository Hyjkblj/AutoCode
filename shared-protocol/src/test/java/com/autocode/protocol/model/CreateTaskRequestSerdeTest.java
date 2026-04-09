package com.autocode.protocol.model;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

public class CreateTaskRequestSerdeTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void canDeserializeLegacyFlatFields() throws Exception {
        String json = "{\n" +
                "  \"projectId\": \"p1\",\n" +
                "  \"prompt\": \"do x\",\n" +
                "  \"assistant\": \"coder\",\n" +
                "  \"workspacePath\": \"D:/w\",\n" +
                "  \"agentProfile\": \"coder\",\n" +
                "  \"sessionKey\": \"s1\",\n" +
                "  \"riskPolicy\": \"high\"\n" +
                "}";

        CreateTaskRequest req = MAPPER.readValue(json, CreateTaskRequest.class);
        assertEquals("p1", req.getProjectId());
        assertEquals("do x", req.getPrompt());
        assertEquals("coder", req.getAssistant());
    }

    @Test
    void canDeserializeStructuredFields() throws Exception {
        String json = "{\n" +
                "  \"identity\": {\"projectId\": \"p1\", \"idempotencyKey\": \"k1\"},\n" +
                "  \"intent\": {\"prompt\": \"do x\", \"target\": \"web\", \"exportMode\": \"zip\"},\n" +
                "  \"execution\": {\"workspaceRef\": \"D:/w\", \"agentProfile\": \"coder\", \"sessionKey\": \"s1\"},\n" +
                "  \"risk\": {\"riskPolicy\": \"high\"}\n" +
                "}";

        CreateTaskRequest req = MAPPER.readValue(json, CreateTaskRequest.class);
        assertNotNull(req.getIdentity());
        assertEquals("p1", req.getIdentity().getProjectId());
        assertNotNull(req.getIntent());
        assertEquals("web", req.getIntent().getTarget());
        assertEquals("zip", req.getIntent().getExportMode());
        assertNotNull(req.getExecution());
        assertEquals("D:/w", req.getExecution().getWorkspaceRef());
        assertNotNull(req.getRisk());
        assertEquals("high", req.getRisk().getRiskPolicy());
    }

    @Test
    void serialization_roundtrip_smoke() throws Exception {
        CreateTaskRequest req = new CreateTaskRequest();
        req.setProjectId("p1");
        req.setPrompt("do x");
        req.setAssistant("coder");
        req.setIdentity(new CreateTaskRequest.Identity());
        req.getIdentity().setProjectId("p1");
        req.getIdentity().setIdempotencyKey("k1");
        req.setIntent(new CreateTaskRequest.Intent());
        req.getIntent().setPrompt("do x");
        req.getIntent().setTarget("web");
        req.getIntent().setTemplateId("web-basic");
        req.getIntent().setExportMode("zip");
        req.getIntent().setOptions(Map.of("templateDigest", "sha256:abc"));

        String json = MAPPER.writeValueAsString(req);
        CreateTaskRequest restored = MAPPER.readValue(json, CreateTaskRequest.class);
        assertEquals("p1", restored.getProjectId());
        assertEquals("p1", restored.getIdentity().getProjectId());
        assertEquals("web", restored.getIntent().getTarget());
        assertEquals("web-basic", restored.getIntent().getTemplateId());
        assertEquals("zip", restored.getIntent().getExportMode());
    }
}
