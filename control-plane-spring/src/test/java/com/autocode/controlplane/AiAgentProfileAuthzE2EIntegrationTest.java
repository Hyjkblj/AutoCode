package com.autocode.controlplane;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureMockMvc
class AiAgentProfileAuthzE2EIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void aiAgentProfileTaskShouldCompleteViaAssignedNodeE2E() throws Exception {
        String profile = uniqueAiProfile();
        String nodeId = "node-ai-e2e-main";
        registerNode(nodeId, "ai-agent,events,approval,profile:" + profile);
        String taskId = createTask("ai-agent done closure", profile);

        String polledTaskId = pollTaskId(nodeId, profile, "ag-a");
        assertEquals(taskId, polledTaskId);

        String outputEvent = """
                {
                  "event": {
                    "eventId": "evt-ai-e2e-output-1",
                    "type": "ASSISTANT_OUTPUT",
                    "assistant": "ai-agent",
                    "payload": {
                      "stage": "orchestrator",
                      "message": "working"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", nodeId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(outputEvent))
                .andExpect(status().isOk());

        String doneEvent = """
                {
                  "event": {
                    "eventId": "evt-ai-e2e-done-1",
                    "type": "TASK_DONE",
                    "assistant": "ai-agent",
                    "payload": {
                      "result": "completed"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", nodeId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(doneEvent))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("DONE"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("DONE"))
                .andExpect(jsonPath("$.payload.agentProfile").value(profile));
    }

    @Test
    void aiAgentProfilePollShouldRespectProfileAndTokenBoundaries() throws Exception {
        String profile = uniqueAiProfile();
        String nodeId = "node-ai-poll-authz";
        registerNode(nodeId, "ai-agent,events,approval,profile:" + profile);
        String taskId = createTask("ai-agent poll authz", profile);

        String mismatchedProfile = "mismatch-" + Long.toHexString(System.nanoTime());
        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", nodeId)
                        .param("profile", mismatchedProfile))
                .andExpect(status().isNoContent());

        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("Authorization", "Bearer op-a")
                        .param("nodeId", nodeId)
                        .param("profile", profile))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("invalid agent token"));

        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("X-Agent-Token", "ag-b")
                        .param("nodeId", nodeId)
                        .param("profile", profile))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("invalid agent token"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("X-Agent-Token", "ag-a"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("invalid operator token"));

        String polledTaskId = pollTaskId(nodeId, profile, "ag-a");
        assertEquals(taskId, polledTaskId);
    }

    @Test
    void aiAgentFixLoopFailureShouldCloseTaskAsFailedE2E() throws Exception {
        String profile = uniqueAiProfile();
        String nodeId = "node-ai-fix-loop";
        registerNode(nodeId, "ai-agent,events,approval,profile:" + profile);
        String taskId = createTask("ai-agent fix loop exhausted", profile);

        String polledTaskId = pollTaskId(nodeId, profile, "ag-a");
        assertEquals(taskId, polledTaskId);

        String failedEvent = """
                {
                  "event": {
                    "eventId": "evt-ai-fix-loop-failed-1",
                    "type": "TASK_FAILED",
                    "assistant": "ai-agent",
                    "payload": {
                      "reason": "fix_loop_exhausted",
                      "attempt": 3,
                      "maxAttempts": 3,
                      "lastTestError": "AssertionError: expected 200 got 500"
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "ag-a")
                        .param("nodeId", nodeId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(failedEvent))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("FAILED"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload.status").value("FAILED"))
                .andExpect(jsonPath("$.payload.agentProfile").value(profile));
    }

    private void registerNode(String nodeId, String capabilities) throws Exception {
        String payload = """
                {
                  "nodeId": "%s",
                  "version": "py-agent-1",
                  "capabilities": "%s"
                }
                """.formatted(nodeId, capabilities);

        mockMvc.perform(post("/api/v1/agent/register")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.nodeId").value(nodeId));
    }

    private String createTask(String prompt, String profile) throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "%s",
                  "agentProfile": "%s"
                }
                """.formatted(prompt, profile);

        String response = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.agentProfile").value(profile))
                .andReturn().getResponse().getContentAsString();

        return objectMapper.readTree(response).path("payload").path("taskId").asText();
    }

    private String pollTaskId(String nodeId, String profile, String token) throws Exception {
        String response = mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .header("X-Agent-Token", token)
                        .param("nodeId", nodeId)
                        .param("profile", profile))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(response).path("payload").path("taskId").asText();
    }

    private String uniqueAiProfile() {
        return "ai-agent-" + Long.toHexString(System.nanoTime());
    }
}
