package com.autocode.controlplane;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.autocode.controlplane.persistence.entity.ProjectMembershipEntity;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.AuditLogRepository;
import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;

import java.time.Instant;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {
        "artifacts.download.shared-token=test-download-token",
        "artifacts.storage.base-dir=./build/test-artifacts"
})
@AutoConfigureMockMvc
class ArtifactsIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserEntityRepository userRepository;

    @Autowired
    private ProjectMembershipEntityRepository membershipRepository;

    @Autowired
    private AuditLogRepository auditLogRepository;

    @BeforeEach
    void setup() {
        // Test fixture: enable method-security authorization in token mode by seeding a user + membership.
        // TokenAuthFilter sets principal name to "operator" for operator bearer tokens.
        UserEntity user = userRepository.findByUsername("operator").orElseGet(() -> {
            UserEntity u = new UserEntity();
            u.setUserId("usr_operator");
            u.setUsername("operator");
            u.setPasswordHash("x");
            u.setEnabled(true);
            u.setCreatedAt(Instant.now());
            return userRepository.save(u);
        });

        ProjectMembershipEntity membership = new ProjectMembershipEntity();
        membership.setProjectId("proj-1");
        membership.setUserId(user.getUserId());
        membership.setRoleName("ADMIN");
        membershipRepository.save(membership);
    }

    @Test
    void uploadListDownloadAndAuditChainPrevHashIsValid() throws Exception {
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

        MockMultipartFile file = new MockMultipartFile(
                "file",
                "export.zip",
                "application/zip",
                "zip-bytes".getBytes()
        );

        mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.artifactId").exists())
                .andExpect(jsonPath("$.payload.sha256").exists());

        MvcResult listRes = mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.items.length()").value(1))
                .andReturn();

        String listJson = listRes.getResponse().getContentAsString();
        String artifactId = objectMapper.readTree(listJson).path("payload").path("items").get(0).path("artifactId").asText();

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, artifactId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, artifactId)
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    byte[] bytes = result.getResponse().getContentAsByteArray();
                    if (bytes.length == 0) {
                        throw new AssertionError("downloaded bytes should not be empty");
                    }
                });

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", taskId, artifactId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", taskId, artifactId)
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    String cd = result.getResponse().getHeader("Content-Disposition");
                    if (cd == null || !cd.toLowerCase().contains("inline")) {
                        throw new AssertionError("preview should use inline Content-Disposition: " + cd);
                    }
                });

        mockMvc.perform(get("/api/v1/audits/export")
                        .param("taskId", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.chainValid").value(true))
                .andExpect(jsonPath("$.payload.count").value(org.hamcrest.Matchers.greaterThanOrEqualTo(3)));
    }

    @Test
    void auditExportShouldMarkInvalidWhenNonFirstEntryMissesPrevHash() throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "audit chain strictness"
                }
                """;

        String createResponse = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        MockMultipartFile file = new MockMultipartFile(
                "file",
                "export.zip",
                "application/zip",
                "zip-bytes".getBytes()
        );

        mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk());

        var logs = auditLogRepository.findByTaskIdOrderByCreatedAtAscAuditIdAsc(taskId);
        assertTrue(logs.size() >= 2, "expected at least two audit entries");

        var second = logs.get(1);
        second.setPrevHash(null);
        auditLogRepository.saveAndFlush(second);

        mockMvc.perform(get("/api/v1/audits/export")
                        .param("taskId", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.chainValid").value(false));
    }

    @Test
    void artifactsEndpointsReturn404WhenTaskMissing() throws Exception {
        String missingTaskId = "tsk_missing_1";
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "export.zip",
                "application/zip",
                "zip-bytes".getBytes()
        );

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts", missingTaskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", missingTaskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", missingTaskId, "art_missing_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", missingTaskId, "art_missing_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));
    }

    @Test
    void artifactsReturn404ForNonMember() throws Exception {
        // Create a task under proj-1 while we still have membership.
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "codex",
                  "prompt": "generate app"
                }
                """;

        String createResponse = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        // Upload an artifact as agent (upload is allowed for agent regardless of membership).
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "export.zip",
                "application/zip",
                "zip-bytes".getBytes()
        );

        mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true));

        // Remove membership: subsequent artifacts access should be non-enumerable (404).
        membershipRepository.deleteAll();

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        // Non-members must also not be able to download (even with a valid shared token),
        // otherwise artifacts become enumerable via download probing.
        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, "art_any_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", taskId, "art_any_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));
        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/derived", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(get("/api/v1/audits/export")
                        .param("taskId", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        // M2: other task-scoped operator APIs must also mask existence (not 403).
        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer operator-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer operator-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));
    }
}
