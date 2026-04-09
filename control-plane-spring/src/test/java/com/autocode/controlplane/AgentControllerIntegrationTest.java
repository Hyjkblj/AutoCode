package com.autocode.controlplane;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasItem;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureMockMvc
class AgentControllerIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private com.autocode.controlplane.persistence.repo.TaskEntityRepository taskEntityRepository;

    @Autowired
    private PlatformTransactionManager transactionManager;

    @Test
    void registerShouldPersistCapabilitiesAndExposeViaNodesList() throws Exception {
        String capabilities = "{\"profiles\":[\"ai-agent\",\"coder\"],\"runtime\":{\"lang\":\"python\",\"version\":\"3.12\"}}";

        String payload = """
                {
                  "nodeId": "node_cap_1",
                  "version": "1.2.3",
                  "capabilities": "%s"
                }
                """.formatted(capabilities.replace("\"", "\\\""));

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value("node_cap_1"))
                .andExpect(jsonPath("$.payload.version").value("1.2.3"))
                .andExpect(jsonPath("$.payload.online").value(true))
                .andExpect(jsonPath("$.payload.capabilities").value(capabilities));

        mockMvc.perform(get("/api/v1/agent/nodes")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload[*].nodeId", hasItem("node_cap_1")))
                .andExpect(jsonPath("$.payload[*].capabilities", hasItem(capabilities)));
    }

    @Test
    void registerShouldAllowCapabilitiesOmitted() throws Exception {
        String payload = """
                {
                  "nodeId": "node_cap_2",
                  "version": "2.0.0"
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value("node_cap_2"))
                .andExpect(jsonPath("$.payload.version").value("2.0.0"));

        mockMvc.perform(get("/api/v1/agent/nodes")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload[*].nodeId", hasItem("node_cap_2")));
    }

    @Test
    void registerShouldRejectOperatorTokenWithoutAgentToken() throws Exception {
        String payload = """
                {
                  "nodeId": "node_cap_3",
                  "version": "3.0.0"
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("invalid agent token"));
    }

    @Test
    void registerShouldRejectTooLongNodeId() throws Exception {
        String nodeId = "n".repeat(65);
        String payload = """
                {
                  "nodeId": "%s",
                  "version": "1.0.0"
                }
                """.formatted(nodeId);

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("nodeId")));
    }

    @Test
    void registerShouldRejectTooLargeCapabilitiesPayload() throws Exception {
        String oversized = "x".repeat(8193);
        String payload = """
                {
                  "nodeId": "node_cap_4",
                  "capabilities": "%s"
                }
                """.formatted(oversized);

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("capabilities")));
    }

    @Test
    void registerShouldTrimNodeVersionAndCapabilities() throws Exception {
        String payload = """
                {
                  "nodeId": "  node_cap_5  ",
                  "version": "  5.0.0  ",
                  "capabilities": "  cap-a,cap-b  "
                }
                """;

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value("node_cap_5"))
                .andExpect(jsonPath("$.payload.version").value("5.0.0"))
                .andExpect(jsonPath("$.payload.capabilities").value("cap-a,cap-b"));
    }

    @Test
    void heartbeatShouldKeepExistingVersionAndCapabilities() throws Exception {
        String capabilities = "{\"profiles\":[\"ai-agent\"]}";
        String registerPayload = """
                {
                  "nodeId": "node_keep_1",
                  "version": "9.9.9",
                  "capabilities": "%s"
                }
                """.formatted(capabilities.replace("\"", "\\\""));

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(registerPayload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true));

        String heartbeatPayload = """
                {
                  "nodeId": "node_keep_1"
                }
                """;
        mockMvc.perform(post("/api/v1/agent/heartbeat")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(heartbeatPayload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.version").value("9.9.9"))
                .andExpect(jsonPath("$.payload.capabilities").value(capabilities));
    }

    @Test
    void heartbeatShouldRejectTooLongNodeId() throws Exception {
        String nodeId = "h".repeat(65);
        String payload = """
                {
                  "nodeId": "%s"
                }
                """.formatted(nodeId);

        mockMvc.perform(post("/api/v1/agent/heartbeat")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("nodeId")));
    }

    @Test
    void nextTaskShouldRejectBlankNodeIdParam() throws Exception {
        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", "   "))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("nodeId")));
    }

    @Test
    void nextTaskShouldRejectTooLongNodeIdParam() throws Exception {
        String nodeId = "n".repeat(65);
        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", nodeId))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("nodeId")));
    }

    @Test
    void nextTaskShouldRejectUnregisteredNode() throws Exception {
        String nodeId = "node_unregistered_" + System.nanoTime();
        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", nodeId))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("node not registered"));
    }

    @Test
    void approvalStatusShouldReturn404WhenTaskNotFound() throws Exception {
        mockMvc.perform(get("/api/v1/agent/tasks/{taskId}/approval", "tsk_not_exists")
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isNotFound());
    }

    @Test
    void ingestEventShouldRejectBlankNodeIdParam() throws Exception {
        String taskId = createTaskAndGetId("blank node id guard");
        String payload = """
                {
                  "event": {
                    "eventId": "evt-blank-node-id-1",
                    "type": "ASSISTANT_OUTPUT",
                    "assistant": "codex",
                    "payload": {
                      "message": "hello"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", "   ")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("nodeId")));
    }

    @Test
    void ingestEventShouldRejectUnregisteredNodeIdParam() throws Exception {
        String taskId = createTaskAndGetId("unregistered ingest node");
        String payload = """
                {
                  "event": {
                    "eventId": "evt-unregistered-node-id-1",
                    "type": "ASSISTANT_OUTPUT",
                    "assistant": "codex",
                    "payload": {
                      "message": "hello"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", "node-not-registered-ingest")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("node not registered"));
    }

    @Test
    void ingestEventShouldRejectNodeMismatchForAssignedTask() throws Exception {
        registerNode("node-ingest-a");
        registerNode("node-ingest-b");
        String profile = "guard" + Long.toHexString(System.nanoTime());
        String taskId = createTaskAndGetId("assigned node mismatch guard", profile);
        assignTaskToNode(taskId, "node-ingest-a");
        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.assignedNodeId").value("node-ingest-a"));

        String payload = """
                {
                  "event": {
                    "eventId": "evt-assigned-node-mismatch-1",
                    "type": "ASSISTANT_OUTPUT",
                    "assistant": "codex",
                    "payload": {
                      "message": "should be rejected"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", "node-ingest-b")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("forbidden"));
    }

    private void registerNode(String nodeId) throws Exception {
        String payload = """
                {
                  "nodeId": "%s",
                  "version": "1.0.0"
                }
                """.formatted(nodeId);
        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk());
    }

    private String createTaskAndGetId(String prompt) throws Exception {
        return createTaskAndGetId(prompt, "coder");
    }

    private String createTaskAndGetId(String prompt, String agentProfile) throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "%s",
                  "agentProfile": "%s"
                }
                """.formatted(prompt, agentProfile);
        String response = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(response).path("payload").path("taskId").asText();
    }

    private void assignTaskToNode(String taskId, String nodeId) {
        Instant now = Instant.now();
        TransactionTemplate template = new TransactionTemplate(transactionManager);
        Integer claimed = template.execute(status ->
                taskEntityRepository.claimQueuedTask(taskId, nodeId, now, now.plusSeconds(60))
        );
        assertEquals(1, claimed == null ? 0 : claimed, "expected queued task to be claimed for test setup");
    }
}
