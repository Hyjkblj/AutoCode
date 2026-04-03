package com.autocode.controlplane;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class ProtocolValidationIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void agentEventWithUnsupportedVersionShouldReturn400() throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "test proto",
                  "agentProfile": "coder"
                }
                """;
        String createResp = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        String taskId = objectMapper.readTree(createResp).path("payload").path("taskId").asText();

        String badEvent = """
                {
                  "event": {
                    "eventId": "evt-bad-ver-1",
                    "type": "ASSISTANT_OUTPUT",
                    "assistant": "codex",
                    "eventVersion": 99,
                    "payload": {
                      "message": "hi"
                    }
                  }
                }
                """;
        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(badEvent))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false));
    }

    @Test
    void approvalRequiredWithoutApprovalIdShouldReturn400() throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "test proto 2",
                  "agentProfile": "coder"
                }
                """;
        String createResp = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        String taskId = objectMapper.readTree(createResp).path("payload").path("taskId").asText();

        String badEvent = """
                {
                  "event": {
                    "eventId": "evt-bad-approval-1",
                    "type": "APPROVAL_REQUIRED",
                    "assistant": "codex",
                    "payload": {
                      "action": "run_command",
                      "command": "whoami"
                    }
                  }
                }
                """;
        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(badEvent))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").exists());
    }

    @Test
    void artifactReadyWithInvalidBuildMetadataShouldReturn400() throws Exception {
        String taskId = createTask("runtime metadata validation");

        String badEvent = """
                {
                  "event": {
                    "eventId": "evt-bad-artifact-build-1",
                    "type": "ARTIFACT_READY",
                    "assistant": "codex",
                    "payload": {
                      "artifact": {
                        "artifactId": "art_1",
                        "type": "zip",
                        "build": {}
                      }
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(badEvent))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("artifact.build.command")));
    }

    @Test
    void deployPlanWithoutRequestIdShouldReturn400() throws Exception {
        String taskId = createTask("deploy payload validation");

        String badEvent = """
                {
                  "event": {
                    "eventId": "evt-bad-deploy-plan-1",
                    "type": "DEPLOY_PLAN",
                    "assistant": "codex",
                    "payload": {
                      "environment": "staging",
                      "artifact": {
                        "artifactId": "art_2",
                        "type": "zip"
                      }
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(badEvent))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("event.payload.requestId")));
    }

    private String createTask(String prompt) throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "%s",
                  "agentProfile": "coder"
                }
                """.formatted(prompt.replace("\"", "\\\""));
        String createResp = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(createResp).path("payload").path("taskId").asText();
    }
}

