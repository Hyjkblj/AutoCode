package com.autocode.controlplane.api;

import com.autocode.controlplane.artifacts.application.ArtifactForbiddenException;
import com.autocode.controlplane.artifacts.application.ArtifactNotFoundException;
import com.autocode.controlplane.artifacts.application.HostedArtifactSiteService;
import com.autocode.controlplane.artifacts.application.TaskNotFoundException;
import com.autocode.controlplane.persistence.entity.ArtifactEntity;
import com.autocode.controlplane.persistence.repo.ArtifactEntityRepository;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.util.UriUtils;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.stream.Collectors;

@RestController
public class ArtifactShortLinkController {
    private final ArtifactEntityRepository artifactRepository;
    private final HostedArtifactSiteService hostedArtifactSiteService;
    private final String sharedDownloadToken;

    public ArtifactShortLinkController(
            ArtifactEntityRepository artifactRepository,
            HostedArtifactSiteService hostedArtifactSiteService,
            @Value("${artifacts.download.shared-token:}") String sharedDownloadToken
    ) {
        this.artifactRepository = artifactRepository;
        this.hostedArtifactSiteService = hostedArtifactSiteService;
        this.sharedDownloadToken = sharedDownloadToken == null ? "" : sharedDownloadToken.trim();
    }

    @GetMapping("/s/{artifactId}")
    public ResponseEntity<Void> redirectToHostedSite(
            @PathVariable("artifactId") String artifactId,
            HttpServletRequest request
    ) {
        String normalizedArtifactId = artifactId == null ? "" : artifactId.trim();
        if (normalizedArtifactId.isBlank() || sharedDownloadToken.isBlank()) {
            return ResponseEntity.notFound().build();
        }

        ArtifactEntity artifact = artifactRepository.findById(normalizedArtifactId).orElse(null);
        if (artifact == null) {
            return ResponseEntity.notFound().build();
        }

        String taskId = artifact.getTaskId();
        HostedArtifactSiteService.HostedSiteInfo hostedSiteInfo;
        try {
            hostedSiteInfo = hostedArtifactSiteService.ensureHostedSite(taskId, normalizedArtifactId, sharedDownloadToken);
        } catch (ArtifactForbiddenException ex) {
            return ResponseEntity.status(404).build();
        } catch (ArtifactNotFoundException | TaskNotFoundException | IllegalArgumentException ex) {
            return ResponseEntity.notFound().build();
        }

        String location = buildHostedSiteLocation(
                request,
                taskId,
                normalizedArtifactId,
                hostedSiteInfo.entryPath(),
                sharedDownloadToken
        );
        return ResponseEntity.status(302)
                .header(HttpHeaders.LOCATION, location)
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .build();
    }

    private String buildHostedSiteLocation(
            HttpServletRequest request,
            String taskId,
            String artifactId,
            String entryPath,
            String token
    ) {
        String contextPath = request.getContextPath() == null ? "" : request.getContextPath();
        String encodedTaskId = UriUtils.encodePathSegment(taskId, StandardCharsets.UTF_8);
        String encodedArtifactId = UriUtils.encodePathSegment(artifactId, StandardCharsets.UTF_8);
        String encodedEntry = encodePath(entryPath);
        StringBuilder sb = new StringBuilder();
        sb.append(contextPath)
                .append("/api/v1/tasks/")
                .append(encodedTaskId)
                .append("/artifacts/")
                .append(encodedArtifactId)
                .append("/site/");
        if (!encodedEntry.isBlank()) {
            sb.append(encodedEntry);
        }
        if (token != null && !token.isBlank()) {
            sb.append("?token=").append(UriUtils.encodeQueryParam(token, StandardCharsets.UTF_8));
        }
        return sb.toString();
    }

    private String encodePath(String path) {
        String normalized = path == null ? "" : path.replace('\\', '/');
        return Arrays.stream(normalized.split("/"))
                .filter(segment -> !segment.isBlank())
                .map(segment -> UriUtils.encodePathSegment(segment, StandardCharsets.UTF_8))
                .collect(Collectors.joining("/"));
    }
}
