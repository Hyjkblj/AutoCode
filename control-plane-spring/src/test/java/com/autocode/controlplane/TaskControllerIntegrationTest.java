/**
 * Integration test for task controller endpoints (create/query/events).
 */
package com.autocode.controlplane;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureMockMvc
class TaskControllerIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void createTaskRequiresOperatorToken() throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "fix null pointer"
                }
                """;

        mockMvc.perform(post("/api/v1/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void nonApiEndpointsShouldNotBePermitAllInTokenMode() throws Exception {
        mockMvc.perform(get("/api/v1/agent/nodes"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void agentEndpointShouldRejectOperatorBearerToken() throws Exception {
        mockMvc.perform(get("/api/v1/agent/tasks/next")
                        .param("nodeId", "node-a")
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false));
    }

    @Test
    void operatorEndpointShouldRejectAgentTokenOnly() throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "should fail with agent token"
                }
                """;

        mockMvc.perform(post("/api/v1/tasks")
                        .header("X-Agent-Token", "ag-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.ok").value(false));
    }

    @Test
    void operatorTokenRotationShouldAcceptAnyConfiguredToken() throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "token rotation"
                }
                """;
        mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-b")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void createTaskIsIdempotentWhenHeaderProvided() throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "fix null pointer"
                }
                """;

        String responseOne = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .header("Idempotency-Key", "idem-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andReturn().getResponse().getContentAsString();

        String responseTwo = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .header("Idempotency-Key", "idem-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andReturn().getResponse().getContentAsString();

        String taskOne = objectMapper.readTree(responseOne).path("payload").path("taskId").asText();
        String taskTwo = objectMapper.readTree(responseTwo).path("payload").path("taskId").asText();

        org.junit.jupiter.api.Assertions.assertEquals(taskOne, taskTwo);
    }

    @Test
    void eventsEndpointSupportsLastSeqAlias() throws Exception {
        String createResponse = createTask("seq alias");
        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        // lastSeq=0 should return events including TASK_CREATED at seq>=1
        mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer op-a")
                        .param("lastSeq", "0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload").isArray());

        // legacy lastEventId should behave the same
        mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer op-a")
                        .param("lastEventId", "0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.payload").isArray());
    }

    @Test
    void createTaskShouldExposeSessionIdInSummary() throws Exception {
        String response = createTask("session id field");
        String sessionId = objectMapper.readTree(response).path("payload").path("sessionId").asText();

        org.junit.jupiter.api.Assertions.assertTrue(sessionId != null && sessionId.startsWith("ses_"));
    }

    private String createTask(String prompt) throws Exception {
        String payload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "%s"
                }
                """.formatted(prompt.replace("\"", "\\\""));
        return mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer op-a")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andReturn().getResponse().getContentAsString();
    }
}
