/**
 * Task artifacts API (B-stage): upload/list/download/preview.
 *
 * Notes:
 * - Upload/list are JSON endpoints using shared-protocol gateway envelope.
 * - Download/preview return bytes and may additionally enforce shared-token based on config.
 */
package com.autocode.controlplane.api;

import com.autocode.controlplane.artifacts.application.ArtifactsService;
import com.autocode.controlplane.artifacts.application.HostedArtifactSiteService;
import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.protocol.model.GatewayResponse;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.ResponseCookie;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;
import org.springframework.web.util.UriUtils;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/tasks/{taskId}/artifacts")
public class ArtifactsController {
    private static final String SITE_TOKEN_COOKIE = "ac_site_token";

    private final ArtifactsService artifactsService;
    private final HostedArtifactSiteService hostedArtifactSiteService;
    private final String hostingPublicBaseUrl;
    private final String sharedDownloadToken;

    public ArtifactsController(
            ArtifactsService artifactsService,
            HostedArtifactSiteService hostedArtifactSiteService,
            @Value("${artifacts.hosting.public-base-url:}") String hostingPublicBaseUrl,
            @Value("${artifacts.download.shared-token:}") String sharedDownloadToken
    ) {
        this.artifactsService = artifactsService;
        this.hostedArtifactSiteService = hostedArtifactSiteService;
        this.hostingPublicBaseUrl = hostingPublicBaseUrl == null ? "" : hostingPublicBaseUrl.trim();
        this.sharedDownloadToken = sharedDownloadToken == null ? "" : sharedDownloadToken.trim();
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

    @GetMapping("/{artifactId}/site-url")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<GatewayResponse> siteUrl(
            @PathVariable("taskId") String taskId,
            @PathVariable("artifactId") String artifactId,
            HttpServletRequest request
    ) {
        HostedArtifactSiteService.HostedSiteInfo siteInfo =
                hostedArtifactSiteService.ensureHostedSite(taskId, artifactId, null);
        String url = buildSiteUrl(request, taskId, artifactId, siteInfo.entryPath(), null);
        String shareUrl = sharedDownloadToken.isBlank()
                ? null
                : buildSiteUrl(request, taskId, artifactId, siteInfo.entryPath(), sharedDownloadToken);
        Map<String, Object> payload = new HashMap<>();
        payload.put("taskId", taskId);
        payload.put("artifactId", artifactId);
        payload.put("entryPath", siteInfo.entryPath());
        payload.put("url", url);
        payload.put("shareUrl", shareUrl);
        payload.put("tokenized", shareUrl != null);
        return ResponseEntity.ok(GatewayResponses.ok(payload));
    }

    @GetMapping({"/{artifactId}/site", "/{artifactId}/site/", "/{artifactId}/site/**"})
    public ResponseEntity<StreamingResponseBody> hostedSite(
            @PathVariable("taskId") String taskId,
            @PathVariable("artifactId") String artifactId,
            @RequestParam(value = "token", required = false) String token,
            @CookieValue(value = SITE_TOKEN_COOKIE, required = false) String tokenCookie,
            HttpServletRequest request
    ) {
        String effectiveToken = (token != null && !token.isBlank())
                ? token.trim()
                : (tokenCookie == null ? null : tokenCookie.trim());
        String relativePath = extractSiteRelativePath(request, taskId, artifactId);
        HostedArtifactSiteService.HostedFile hostedFile =
                hostedArtifactSiteService.resolveHostedFile(taskId, artifactId, relativePath, effectiveToken);

        StreamingResponseBody body = outputStream -> {
            try (InputStream in = Files.newInputStream(hostedFile.filePath())) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    if (n == 0) continue;
                    outputStream.write(buf, 0, n);
                }
            }
        };

        ResponseEntity.BodyBuilder builder = ResponseEntity.ok()
                .contentType(safeMediaType(hostedFile.contentType()))
                .header(HttpHeaders.CACHE_CONTROL, "no-store");
        if (token != null && !token.isBlank() && !sharedDownloadToken.isBlank() && sharedDownloadToken.equals(token.trim())) {
            ResponseCookie cookie = ResponseCookie.from(SITE_TOKEN_COOKIE, token.trim())
                    .httpOnly(true)
                    .sameSite("Lax")
                    .path(siteTokenCookiePath(taskId, artifactId))
                    .maxAge(Duration.ofHours(12))
                    .build();
            builder.header(HttpHeaders.SET_COOKIE, cookie.toString());
        }
        return builder.body(body);
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

    private String extractSiteRelativePath(HttpServletRequest request, String taskId, String artifactId) {
        String uri = request.getRequestURI();
        String contextPath = request.getContextPath() == null ? "" : request.getContextPath();
        String prefix = contextPath + "/api/v1/tasks/" + taskId + "/artifacts/" + artifactId + "/site";
        if (!uri.startsWith(prefix)) {
            return "";
        }
        String rest = uri.substring(prefix.length());
        if (rest.startsWith("/")) {
            rest = rest.substring(1);
        }
        return rest.isBlank() ? "" : UriUtils.decode(rest, StandardCharsets.UTF_8);
    }

    private String buildSiteUrl(
            HttpServletRequest request,
            String taskId,
            String artifactId,
            String entryPath,
            String token
    ) {
        String base = resolvePublicBaseUrl(request);
        String encodedTask = UriUtils.encodePathSegment(taskId, StandardCharsets.UTF_8);
        String encodedArtifact = UriUtils.encodePathSegment(artifactId, StandardCharsets.UTF_8);
        String encodedEntry = encodePath(entryPath);
        StringBuilder sb = new StringBuilder();
        sb.append(base)
                .append("/api/v1/tasks/")
                .append(encodedTask)
                .append("/artifacts/")
                .append(encodedArtifact)
                .append("/site/")
                .append(encodedEntry);
        if (token != null && !token.isBlank()) {
            sb.append("?token=").append(UriUtils.encodeQueryParam(token, StandardCharsets.UTF_8));
        }
        return sb.toString();
    }

    private String resolvePublicBaseUrl(HttpServletRequest request) {
        if (!hostingPublicBaseUrl.isBlank()) {
            return trimTrailingSlash(hostingPublicBaseUrl);
        }
        String current = ServletUriComponentsBuilder.fromCurrentContextPath().build().toUriString();
        return trimTrailingSlash(current);
    }

    private String encodePath(String path) {
        String normalized = path == null ? "" : path.replace('\\', '/');
        return Arrays.stream(normalized.split("/"))
                .filter(segment -> !segment.isBlank())
                .map(segment -> UriUtils.encodePathSegment(segment, StandardCharsets.UTF_8))
                .collect(Collectors.joining("/"));
    }

    private String siteTokenCookiePath(String taskId, String artifactId) {
        return "/api/v1/tasks/" + taskId + "/artifacts/" + artifactId + "/site";
    }

    private String trimTrailingSlash(String raw) {
        String value = raw == null ? "" : raw.trim();
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private MediaType safeMediaType(String raw) {
        if (raw == null || raw.isBlank()) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
        try {
            return MediaType.parseMediaType(raw);
        } catch (IllegalArgumentException ex) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }

    // GatewayResponses centralizes response construction for gateway-style endpoints.
}

