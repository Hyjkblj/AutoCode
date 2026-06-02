package com.autocode.artifact;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Integration tests for {@link ArtifactController}.
 *
 * Uses an in-memory H2 database (test profile) so no external MySQL is required.
 * Tests cover the four core endpoints:
 *  - POST /artifacts        (store)
 *  - GET  /artifacts/{id}   (metadata)
 *  - GET  /artifacts/{id}/download (download)
 *  - DELETE /artifacts/{id} (delete)
 *
 * Requirements: 11.1, 11.2, 14.1–14.7
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ArtifactControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ArtifactRepository artifactRepository;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        artifactRepository.deleteAll();
    }

    // -------------------------------------------------------------------------
    // POST /artifacts — store new artifact
    // -------------------------------------------------------------------------

    @Test
    void upload_validFile_returns201WithMetadata() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "hello.txt", MediaType.TEXT_PLAIN_VALUE, "hello world".getBytes());

        MvcResult result = mockMvc.perform(multipart("/artifacts")
                        .file(file)
                        .param("taskId", "task-001"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.artifactId").isNotEmpty())
                .andExpect(jsonPath("$.taskId").value("task-001"))
                .andExpect(jsonPath("$.name").value("hello.txt"))
                .andExpect(jsonPath("$.sizeBytes").value(11))
                .andExpect(jsonPath("$.sha256").isNotEmpty())
                .andExpect(jsonPath("$.createdAt").isNotEmpty())
                .andReturn();

        // Verify persisted in DB
        String body = result.getResponse().getContentAsString();
        @SuppressWarnings("unchecked")
        Map<String, Object> response = objectMapper.readValue(body, Map.class);
        String artifactId = (String) response.get("artifactId");
        assertThat(artifactRepository.findById(artifactId)).isPresent();
    }

    @Test
    void upload_missingFile_returns400() throws Exception {
        mockMvc.perform(multipart("/artifacts")
                        .param("taskId", "task-001"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void upload_missingTaskId_returns400() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "hello.txt", MediaType.TEXT_PLAIN_VALUE, "hello".getBytes());

        mockMvc.perform(multipart("/artifacts")
                        .file(file))
                .andExpect(status().isBadRequest());
    }

    // -------------------------------------------------------------------------
    // GET /artifacts/{id} — retrieve artifact metadata
    // -------------------------------------------------------------------------

    @Test
    void getMetadata_existingArtifact_returns200() throws Exception {
        String artifactId = uploadArtifact("task-002", "data.bin", "binary data".getBytes());

        mockMvc.perform(get("/artifacts/{id}", artifactId)
                        .param("taskId", "task-002"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.artifactId").value(artifactId))
                .andExpect(jsonPath("$.taskId").value("task-002"))
                .andExpect(jsonPath("$.name").value("data.bin"));
    }

    @Test
    void getMetadata_unknownArtifact_returns404() throws Exception {
        mockMvc.perform(get("/artifacts/{id}", "nonexistent-id")
                        .param("taskId", "task-002"))
                .andExpect(status().isNotFound());
    }

    @Test
    void getMetadata_wrongTaskId_returns404() throws Exception {
        String artifactId = uploadArtifact("task-003", "file.txt", "content".getBytes());

        mockMvc.perform(get("/artifacts/{id}", artifactId)
                        .param("taskId", "wrong-task"))
                .andExpect(status().isNotFound());
    }

    // -------------------------------------------------------------------------
    // GET /artifacts/{id}/download — download artifact file
    // -------------------------------------------------------------------------

    @Test
    void download_existingArtifact_returnsBytes() throws Exception {
        byte[] content = "download me".getBytes();
        String artifactId = uploadArtifact("task-004", "download.txt", content);

        MvcResult result = mockMvc.perform(get("/artifacts/{id}/download", artifactId)
                        .param("taskId", "task-004"))
                .andExpect(status().isOk())
                .andExpect(header().string(
                        "Content-Disposition", "attachment; filename=\"download.txt\""))
                .andExpect(header().string("X-Artifact-Id", artifactId))
                .andReturn();

        assertThat(result.getResponse().getContentAsByteArray()).isEqualTo(content);
    }

    @Test
    void download_unknownArtifact_returns404() throws Exception {
        mockMvc.perform(get("/artifacts/{id}/download", "no-such-id")
                        .param("taskId", "task-004"))
                .andExpect(status().isNotFound());
    }

    // -------------------------------------------------------------------------
    // DELETE /artifacts/{id} — delete artifact
    // -------------------------------------------------------------------------

    @Test
    void delete_existingArtifact_returns204AndRemovesRecord() throws Exception {
        String artifactId = uploadArtifact("task-005", "to-delete.txt", "bye".getBytes());

        mockMvc.perform(delete("/artifacts/{id}", artifactId)
                        .param("taskId", "task-005"))
                .andExpect(status().isNoContent());

        assertThat(artifactRepository.findById(artifactId)).isEmpty();
    }

    @Test
    void delete_unknownArtifact_returns404() throws Exception {
        mockMvc.perform(delete("/artifacts/{id}", "ghost-id")
                        .param("taskId", "task-005"))
                .andExpect(status().isNotFound());
    }

    // -------------------------------------------------------------------------
    // GET /artifacts — list artifacts for a task
    // -------------------------------------------------------------------------

    @Test
    void list_returnsArtifactsForTask() throws Exception {
        uploadArtifact("task-006", "a.txt", "aaa".getBytes());
        uploadArtifact("task-006", "b.txt", "bbb".getBytes());
        uploadArtifact("task-007", "c.txt", "ccc".getBytes()); // different task

        mockMvc.perform(get("/artifacts").param("taskId", "task-006"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.taskId").value("task-006"))
                .andExpect(jsonPath("$.count").value(2))
                .andExpect(jsonPath("$.items").isArray());
    }

    // -------------------------------------------------------------------------
    // GET /actuator/health — health check
    // -------------------------------------------------------------------------

    @Test
    void actuatorHealth_returns200() throws Exception {
        mockMvc.perform(get("/actuator/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Uploads an artifact and returns its ID.
     */
    private String uploadArtifact(String taskId, String filename, byte[] content) throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", filename, MediaType.APPLICATION_OCTET_STREAM_VALUE, content);

        MvcResult result = mockMvc.perform(multipart("/artifacts")
                        .file(file)
                        .param("taskId", taskId))
                .andExpect(status().isCreated())
                .andReturn();

        String body = result.getResponse().getContentAsString();
        @SuppressWarnings("unchecked")
        Map<String, Object> response = objectMapper.readValue(body, Map.class);
        return (String) response.get("artifactId");
    }
}
