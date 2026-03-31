/**
 * Integration test ensuring artifacts aggregation returns patch previews and audit logs.
 */
package com.autocode.controlplane;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class ArtifactsIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void artifactsIncludesPatchAndAuditLogs() throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "refactor service"
                }
                """;

        String createResponse = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        JsonNode createTree = objectMapper.readTree(createResponse);
        String taskId = createTree.path("payload").path("taskId").asText();

        String eventPayload = """
                {
                  "event": {
                    "eventId": "evt-artifacts-1",
                    "type": "FILE_PATCH_PREVIEW",
                    "assistant": "codex",
                    "payload": {
                      "file": "src/main/java/App.java",
                      "added": 3,
                      "removed": 1
                    }
                  }
                }
                """;

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(eventPayload))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.patchPreviews.length()").value(1))
                .andExpect(jsonPath("$.payload.auditLogs.length()").value(org.hamcrest.Matchers.greaterThanOrEqualTo(2)));
    }
}
