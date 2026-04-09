/**
 * Task artifacts API (B-stage): upload/list/download/preview.
 *
 * Notes:
 * - Upload/list are JSON endpoints using shared-protocol gateway envelope.
 * - Download/preview return bytes with the same shared-token gate; preview uses inline disposition for UI.
 */
package com.autocode.controlplane.api;

import com.autocode.controlplane.artifacts.application.ArtifactsService;
import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.protocol.model.GatewayResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/tasks/{taskId}/artifacts")
public class ArtifactsController {
    private final ArtifactsService artifactsService;

    public ArtifactsController(ArtifactsService artifactsService) {
        this.artifactsService = artifactsService;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    // Use #p0 instead of named params to avoid requiring Java -parameters for SpEL.
    @PreAuthorize("hasAnyAuthority('ROLE_AGENT','ROLE_ADMIN') or @projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<GatewayResponse> upload(
            @PathVariable("taskId") String taskId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "name", required = false) String name
    ) throws IOException {
        if (file == null || file.isEmpty()) {
            return ResponseEntity.badRequest().body(GatewayResponses.error("file is required"));
        }
        String artifactName = (name == null || name.isBlank()) ? file.getOriginalFilename() : name;
        ArtifactRecord record = artifactsService.upload(taskId, artifactName, file.getContentType(), file.getInputStream());
        return ResponseEntity.ok(GatewayResponses.ok(toArtifactMap(record)));
    }

    @GetMapping
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<GatewayResponse> list(@PathVariable("taskId") String taskId) {
        List<ArtifactRecord> list = artifactsService.list(taskId);
        List<Map<String, Object>> items = list.stream().map(ArtifactsController::toArtifactMap).toList();
        return ResponseEntity.ok(GatewayResponses.ok(Map.of("taskId", taskId, "items", items)));
    }

    @GetMapping("/{artifactId}/download")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<StreamingResponseBody> download(
            @PathVariable("taskId") String taskId,
            @PathVariable("artifactId") String artifactId,
            @RequestParam(value = "token", required = false) String token
    ) {
        ArtifactContent content = artifactsService.download(taskId, artifactId, token);
        return toStreamingResponse(content, "attachment");
    }

    @GetMapping("/{artifactId}/preview")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<StreamingResponseBody> preview(
            @PathVariable("taskId") String taskId,
            @PathVariable("artifactId") String artifactId,
            @RequestParam(value = "token", required = false) String token
    ) {
        ArtifactContent content = artifactsService.preview(taskId, artifactId, token);
        return toStreamingResponse(content, "inline");
    }

    private static ResponseEntity<StreamingResponseBody> toStreamingResponse(ArtifactContent content, String disposition) {
        ArtifactRecord r = content.record();
        MediaType mediaType = (r.contentType() == null || r.contentType().isBlank())
                ? MediaType.APPLICATION_OCTET_STREAM
                : MediaType.parseMediaType(r.contentType());

        StreamingResponseBody body = outputStream -> {
            try (InputStream in = content.stream()) {
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
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition + "; filename=\"" + safeFilename(r.name()) + "\"")
                .header("X-Artifact-Id", r.artifactId())
                .header("X-Artifact-Sha256", r.sha256())
                .contentLength(r.sizeBytes())
                .body(body);
    }

    private static String safeFilename(String name) {
        if (name == null || name.isBlank()) return "artifact.bin";
        return name.replaceAll("[\\r\\n\\\\\"]", "_");
    }

    private static Map<String, Object> toArtifactMap(ArtifactRecord record) {
        // Keep both legacy and nl2web aliases so clients can migrate field names gradually.
        Map<String, Object> item = new HashMap<>();
        item.put("artifactId", record.artifactId());
        item.put("taskId", record.taskId());
        item.put("name", record.name());
        item.put("fileName", record.name());
        item.put("contentType", record.contentType());
        item.put("mimeType", record.contentType());
        item.put("sizeBytes", record.sizeBytes());
        item.put("size", record.sizeBytes());
        item.put("sha256", record.sha256());
        item.put("createdAt", record.createdAt() == null ? null : record.createdAt().toString());
        return item;
    }

    // GatewayResponses centralizes response construction for gateway-style endpoints.
}

