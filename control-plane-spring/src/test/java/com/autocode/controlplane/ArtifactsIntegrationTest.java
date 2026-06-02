package com.autocode.controlplane;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.autocode.controlplane.persistence.entity.ProjectMembershipEntity;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.AuditLogRepository;
import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = {
        "mvp.auth.jwt.secret=01234567890123456789012345678901",
        "artifacts.download.shared-token=test-download-token",
        "artifacts.download.allow-authenticated-without-shared-token=false",
        "artifacts.storage.base-dir=./build/test-artifacts",
        "artifacts.hosting.base-dir=./build/test-artifacts-hosted"
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

    @Autowired
    private JwtEncoder jwtEncoder;

    private String operatorJwt;

    @BeforeEach
    void setup() {
        // Seed a user + membership for method-security authorization.
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

        // Generate an operator JWT for test requests.
        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject("operator")
                .issuedAt(now)
                .expiresAt(now.plusSeconds(3600))
                .claim("roles", List.of("OPERATOR", "ADMIN"))
                .build();
        JwsHeader jwsHeader = JwsHeader.with(MacAlgorithm.HS256).build();
        operatorJwt = jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claims)).getTokenValue();
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
                        .header("Authorization", "Bearer " + operatorJwt)
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
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.items.length()").value(1))
                .andReturn();

        String listJson = listRes.getResponse().getContentAsString();
        String artifactId = objectMapper.readTree(listJson).path("payload").path("items").get(0).path("artifactId").asText();

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, artifactId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false));

        MvcResult downloadResult = mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, artifactId)
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(request().asyncStarted())
                .andReturn();

        downloadResult.getAsyncResult();
        assertEquals(200, downloadResult.getResponse().getStatus());
        byte[] downloadedBytes = downloadResult.getResponse().getContentAsByteArray();
        if (downloadedBytes.length == 0) {
            throw new AssertionError("downloaded bytes should not be empty");
        }

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", taskId, artifactId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", taskId, artifactId)
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    String cd = result.getResponse().getHeader("Content-Disposition");
                    if (cd == null || !cd.toLowerCase().contains("inline")) {
                        throw new AssertionError("preview should use inline Content-Disposition: " + cd);
                    }
                });

        mockMvc.perform(get("/api/v1/audits/export")
                        .param("taskId", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
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
                        .header("Authorization", "Bearer " + operatorJwt)
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
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.taskId").value(taskId))
                .andExpect(jsonPath("$.payload.chainValid").value(false));
    }

    @Test
    void artifactReadyLifecycleShouldExposeNl2webMetadataAndEnforceDownloadAuth() throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "ai-agent",
                  "prompt": "build a landing page"
                }
                """;

        String createResponse = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer " + operatorJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();
        byte[] zipBytes = "zip-bytes".getBytes();
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "export.zip",
                "application/zip",
                zipBytes
        );

        String uploadResponse = mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.fileName").value("export.zip"))
                .andExpect(jsonPath("$.payload.size").value(zipBytes.length))
                .andExpect(jsonPath("$.payload.mimeType").value("application/zip"))
                .andReturn().getResponse().getContentAsString();

        JsonNode uploadPayload = objectMapper.readTree(uploadResponse).path("payload");
        String artifactId = uploadPayload.path("artifactId").asText();
        String sha256 = uploadPayload.path("sha256").asText();

        String artifactReadyEvent = """
                {
                  "event": {
                    "eventId": "evt-nl2web-artifact-ready-1",
                    "type": "ARTIFACT_READY",
                    "assistant": "ai-agent",
                    "payload": {
                      "kind": "zip",
                      "artifact": {
                        "artifactId": "%s",
                        "type": "zip",
                        "name": "export.zip",
                        "fileName": "export.zip",
                        "hash": "sha256:%s",
                        "sha256": "%s",
                        "size": %d,
                        "mime": "application/zip",
                        "mimeType": "application/zip"
                      }
                    }
                  }
                }
                """.formatted(artifactId, sha256, sha256, zipBytes.length);

        mockMvc.perform(post("/api/v1/agent/tasks/{taskId}/events", taskId)
                        .header("X-Agent-Token", "agent-dev-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(artifactReadyEvent))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true));

        String eventsResponse = mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        JsonNode events = objectMapper.readTree(eventsResponse).path("payload");
        JsonNode readyEvent = null;
        for (JsonNode event : events) {
            if ("evt-nl2web-artifact-ready-1".equals(event.path("eventId").asText())) {
                readyEvent = event;
                break;
            }
        }
        assertTrue(readyEvent != null, "ARTIFACT_READY event should be queryable");
        assertEquals(artifactId, readyEvent.path("payload").path("artifact").path("artifactId").asText());
        assertEquals("export.zip", readyEvent.path("payload").path("artifact").path("fileName").asText());
        assertEquals(zipBytes.length, readyEvent.path("payload").path("artifact").path("size").asInt());
        assertEquals("application/zip", readyEvent.path("payload").path("artifact").path("mimeType").asText());

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.items.length()").value(1))
                .andExpect(jsonPath("$.payload.items[0].artifactId").value(artifactId))
                .andExpect(jsonPath("$.payload.items[0].fileName").value("export.zip"))
                .andExpect(jsonPath("$.payload.items[0].size").value(zipBytes.length))
                .andExpect(jsonPath("$.payload.items[0].mimeType").value("application/zip"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, artifactId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, artifactId)
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    byte[] bytes = result.getResponse().getContentAsByteArray();
                    if (bytes.length == 0) {
                        throw new AssertionError("downloaded bytes should not be empty");
                    }
                });
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
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", missingTaskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", missingTaskId, "art_missing_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", missingTaskId, "art_missing_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
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
                        .header("Authorization", "Bearer " + operatorJwt)
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
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        // Non-members must also not be able to download (even with a valid shared token),
        // otherwise artifacts become enumerable via download probing.
        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/download", taskId, "art_any_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/preview", taskId, "art_any_1")
                        .queryParam("token", "test-download-token")
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));
        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/derived", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(get("/api/v1/audits/export")
                        .param("taskId", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        // M2: other task-scoped operator APIs must also mask existence (not 403).
        mockMvc.perform(get("/api/v1/tasks/{taskId}", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(get("/api/v1/tasks/{taskId}/events", taskId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));

        mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer " + operatorJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false))
                .andExpect(jsonPath("$.error").value("not found"));
    }

    @Test
    void hostedSiteShouldExposeUrlAndServeStaticFilesWithSharedToken() throws Exception {
        String createPayload = """
                {
                  "projectId": "proj-1",
                  "assistant": "ai-agent",
                  "prompt": "build a landing page"
                }
                """;

        String createResponse = mockMvc.perform(post("/api/v1/tasks")
                        .header("Authorization", "Bearer " + operatorJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createPayload))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        String taskId = objectMapper.readTree(createResponse).path("payload").path("taskId").asText();

        Map<String, String> files = new LinkedHashMap<>();
        files.put("index.html", """
                <!doctype html>
                <html>
                <head><link rel="stylesheet" href="styles.css"></head>
                <body><h1>Hello AutoCode</h1><script src="app.js"></script></body>
                </html>
                """);
        files.put("styles.css", "body { font-family: sans-serif; }");
        files.put("app.js", "window.__autocode = 'ok';");

        byte[] zipBytes = buildZip(files);
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "export.zip",
                "application/zip",
                zipBytes
        );

        String uploadResponse = mockMvc.perform(multipart("/api/v1/tasks/{taskId}/artifacts", taskId)
                        .file(file)
                        .header("X-Agent-Token", "agent-dev-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andReturn().getResponse().getContentAsString();

        String artifactId = objectMapper.readTree(uploadResponse).path("payload").path("artifactId").asText();

        mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/site/index.html", taskId, artifactId))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.ok").value(false));

        String urlResponse = mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/site-url", taskId, artifactId)
                        .header("Authorization", "Bearer " + operatorJwt))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.entryPath").value("index.html"))
                .andExpect(jsonPath("$.payload.url").exists())
                .andExpect(jsonPath("$.payload.shareUrl").exists())
                .andReturn().getResponse().getContentAsString();

        JsonNode payload = objectMapper.readTree(urlResponse).path("payload");
        String shareUrl = payload.path("shareUrl").asText();
        String directShareUrl = payload.path("directShareUrl").asText();
        String shortUrl = payload.path("shortUrl").asText();
        assertTrue(directShareUrl.contains("token=test-download-token"));

        String apiPathWithQuery;
        if (shareUrl.contains("/api/v1/tasks/")) {
            apiPathWithQuery = shareUrl.substring(shareUrl.indexOf("/api/v1/tasks/"));
        } else {
            assertEquals(shortUrl, shareUrl, "shareUrl should expose short link when available");
            int shortIdx = shortUrl.indexOf("/s/");
            assertTrue(shortIdx >= 0, "shortUrl should contain short-link path");
            String shortPath = shortUrl.substring(shortIdx);
            String location = mockMvc.perform(get(shortPath))
                    .andExpect(status().isFound())
                    .andReturn()
                    .getResponse()
                    .getHeader(HttpHeaders.LOCATION);
            assertNotNull(location, "short link should redirect to tokenized hosted site");
            assertTrue(location.contains("token=test-download-token"));
            int idx = location.indexOf("/api/v1/tasks/");
            assertTrue(idx >= 0, "redirect location should contain API path");
            apiPathWithQuery = location.substring(idx);
        }
        String indexPath = apiPathWithQuery.substring(0, apiPathWithQuery.indexOf('?'));

        MvcResult indexAsync = mockMvc.perform(get(indexPath)
                        .queryParam("token", "test-download-token"))
                .andExpect(request().asyncStarted())
                .andReturn();
        indexAsync.getAsyncResult();
        MvcResult indexResult = indexAsync;
        assertEquals(200, indexResult.getResponse().getStatus());
        String html = indexResult.getResponse().getContentAsString();
        assertTrue(html.contains("Hello AutoCode"));
        String setCookie = indexResult.getResponse().getHeader(HttpHeaders.SET_COOKIE);
        assertNotNull(setCookie, "site index should set shared-token cookie");

        MvcResult appJsAsync = mockMvc.perform(get("/api/v1/tasks/{taskId}/artifacts/{artifactId}/site/app.js", taskId, artifactId)
                        .queryParam("token", "test-download-token"))
                .andExpect(request().asyncStarted())
                .andReturn();
        appJsAsync.getAsyncResult();
        assertEquals(200, appJsAsync.getResponse().getStatus());
        String js = appJsAsync.getResponse().getContentAsString();
        if (!js.contains("window.__autocode")) {
            throw new AssertionError("expected hosted js content");
        }
    }

    private byte[] buildZip(Map<String, String> files) throws IOException {
        try (ByteArrayOutputStream out = new ByteArrayOutputStream();
             ZipOutputStream zip = new ZipOutputStream(out, StandardCharsets.UTF_8)) {
            for (Map.Entry<String, String> entry : files.entrySet()) {
                zip.putNextEntry(new ZipEntry(entry.getKey()));
                zip.write(entry.getValue().getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
            zip.finish();
            return out.toByteArray();
        }
    }
}
