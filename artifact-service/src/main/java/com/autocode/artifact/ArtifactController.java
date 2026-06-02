package com.autocode.artifact;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * REST controller for the Artifact Service.
 *
 * Endpoints:
 *  GET  /artifacts/{id}          — retrieve artifact metadata
 *  GET  /artifacts/{id}/download — download artifact file
 *  POST /artifacts               — store new artifact
 *  DELETE /artifacts/{id}        — delete artifact
 *
 * The health endpoint is provided automatically by Spring Boot Actuator at
 * {@code GET /actuator/health}.
 *
 * Requirements: 11.1, 11.2, 14.1–14.7
 */
@RestController
@RequestMapping("/artifacts")
public class ArtifactController {

    private static final Logger log = LoggerFactory.getLogger(ArtifactController.class);

    private final ArtifactStorageService storageService;

    public ArtifactController(ArtifactStorageService storageService) {
        this.storageService = storageService;
    }

    // -------------------------------------------------------------------------
    // GET /artifacts/{id}  — retrieve artifact metadata
    // -------------------------------------------------------------------------

    /**
     * Returns artifact metadata as JSON.
     *
     * @param id artifact identifier
     * @return 200 with metadata map, or 404 if not found
     */
    @GetMapping("/{id}")
    public ResponseEntity<Map<String, Object>> getMetadata(
            @PathVariable("id") String id,
            @RequestParam(value = "taskId", required = false) String taskId
    ) {
        String resolvedTaskId = resolveTaskId(taskId, id);
        ArtifactEntity entity = storageService.getMetadata(resolvedTaskId, id);
        return ResponseEntity.ok(toMetadataMap(entity));
    }

    // -------------------------------------------------------------------------
    // GET /artifacts/{id}/download  — download artifact file
    // -------------------------------------------------------------------------

    /**
     * Streams the artifact bytes to the caller with appropriate content-type headers.
     *
     * Requirements: 14.2, 14.6
     *
     * @param id artifact identifier
     * @return 200 streaming response, or 404 if not found
     */
    @GetMapping("/{id}/download")
    public ResponseEntity<StreamingResponseBody> download(
            @PathVariable("id") String id,
            @RequestParam(value = "taskId", required = false) String taskId
    ) {
        String resolvedTaskId = resolveTaskId(taskId, id);
        ArtifactStorageService.ArtifactStream artifactStream = storageService.open(resolvedTaskId, id);
        ArtifactEntity entity = artifactStream.entity();

        MediaType mediaType = parseMediaType(entity.getContentType());
        StreamingResponseBody body = outputStream -> {
            try (InputStream in = artifactStream.stream()) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    if (n == 0) continue;
                    outputStream.write(buf, 0, n);
                }
            }
        };

        return ResponseEntity.ok()
                .contentType(mediaType)
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=\"" + safeFilename(entity.getName()) + "\"")
                .header("X-Artifact-Id", entity.getArtifactId())
                .header("X-Artifact-Sha256", entity.getSha256())
                .contentLength(entity.getSizeBytes())
                .body(body);
    }

    // -------------------------------------------------------------------------
    // POST /artifacts  — store new artifact
    // -------------------------------------------------------------------------

    /**
     * Accepts a multipart file upload and stores it as an artifact.
     *
     * Form parameters:
     *  - {@code file}   (required) — the artifact bytes
     *  - {@code taskId} (required) — owning task identifier
     *  - {@code name}   (optional) — override file name
     *
     * Requirements: 14.1, 14.4
     *
     * @return 201 Created with artifact metadata
     */
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<Map<String, Object>> upload(
            @RequestParam("taskId") String taskId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "name", required = false) String name
    ) throws IOException {
        if (file == null || file.isEmpty()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "file is required"));
        }
        String artifactName = (name == null || name.isBlank()) ? file.getOriginalFilename() : name;
        ArtifactEntity entity = storageService.store(
                taskId, artifactName, file.getContentType(), file.getInputStream());
        return ResponseEntity.status(HttpStatus.CREATED).body(toMetadataMap(entity));
    }

    // -------------------------------------------------------------------------
    // DELETE /artifacts/{id}  — delete artifact
    // -------------------------------------------------------------------------

    /**
     * Deletes an artifact and its stored file.
     *
     * @param id artifact identifier
     * @return 204 No Content on success, 404 if not found
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            @PathVariable("id") String id,
            @RequestParam(value = "taskId", required = false) String taskId
    ) {
        String resolvedTaskId = resolveTaskId(taskId, id);
        storageService.delete(resolvedTaskId, id);
        return ResponseEntity.noContent().build();
    }

    // -------------------------------------------------------------------------
    // GET /artifacts  — list artifacts for a task
    // -------------------------------------------------------------------------

    /**
     * Lists all artifacts for a given task, newest first.
     *
     * @param taskId owning task identifier
     * @return 200 with list of artifact metadata maps
     */
    @GetMapping
    public ResponseEntity<Map<String, Object>> list(
            @RequestParam("taskId") String taskId
    ) {
        List<ArtifactEntity> entities = storageService.listByTask(taskId);
        List<Map<String, Object>> items = entities.stream().map(this::toMetadataMap).toList();
        return ResponseEntity.ok(Map.of("taskId", taskId, "items", items, "count", items.size()));
    }

    // -------------------------------------------------------------------------
    // Exception handlers
    // -------------------------------------------------------------------------

    @ExceptionHandler(ArtifactNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(ArtifactNotFoundException ex) {
        log.debug("artifact not found: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("error", ex.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleBadRequest(IllegalArgumentException ex) {
        log.debug("bad request: {}", ex.getMessage());
        return ResponseEntity.badRequest()
                .body(Map.of("error", ex.getMessage()));
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * When a taskId query param is not provided, we look up the artifact by ID first
     * to resolve the owning taskId. This allows callers to use just the artifact ID.
     */
    private String resolveTaskId(String taskId, String artifactId) {
        if (taskId != null && !taskId.isBlank()) {
            return taskId;
        }
        // Resolve from DB — find the entity by artifactId alone
        return storageService.findTaskIdByArtifactId(artifactId)
                .orElseThrow(() -> new ArtifactNotFoundException("artifact not found: " + artifactId));
    }

    private Map<String, Object> toMetadataMap(ArtifactEntity entity) {
        Map<String, Object> map = new HashMap<>();
        map.put("artifactId", entity.getArtifactId());
        map.put("taskId", entity.getTaskId());
        map.put("name", entity.getName());
        map.put("contentType", entity.getContentType());
        map.put("sizeBytes", entity.getSizeBytes());
        map.put("sha256", entity.getSha256());
        map.put("createdAt", entity.getCreatedAt() == null ? null : entity.getCreatedAt().toString());
        return map;
    }

    private static MediaType parseMediaType(String raw) {
        if (raw == null || raw.isBlank()) return MediaType.APPLICATION_OCTET_STREAM;
        try {
            return MediaType.parseMediaType(raw);
        } catch (IllegalArgumentException ex) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }

    private static String safeFilename(String name) {
        if (name == null || name.isBlank()) return "artifact.bin";
        return name.replaceAll("[\\r\\n\\\\\"]", "_");
    }
}
