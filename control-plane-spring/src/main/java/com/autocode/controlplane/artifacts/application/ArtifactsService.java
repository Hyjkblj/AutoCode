package com.autocode.controlplane.artifacts.application;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.controlplane.artifacts.ports.ArtifactsPort;
import com.autocode.controlplane.artifacts.ports.AuditPort;
import com.autocode.controlplane.artifacts.ports.DownloadAuthzPort;
import com.autocode.controlplane.artifacts.ports.TaskReadPort;
import com.autocode.controlplane.security.ProjectAuthz;
import com.autocode.controlplane.security.SecurityPrincipalUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.util.List;
import java.util.Map;

@Service
public class ArtifactsService {
    private final ArtifactsPort artifactsPort;
    private final DownloadAuthzPort downloadAuthzPort;
    private final AuditPort auditPort;
    private final TaskReadPort taskReadPort;
    private final ProjectAuthz projectAuthz;

    public ArtifactsService(
            ArtifactsPort artifactsPort,
            DownloadAuthzPort downloadAuthzPort,
            AuditPort auditPort,
            TaskReadPort taskReadPort,
            ProjectAuthz projectAuthz
    ) {
        this.artifactsPort = artifactsPort;
        this.downloadAuthzPort = downloadAuthzPort;
        this.auditPort = auditPort;
        this.taskReadPort = taskReadPort;
        this.projectAuthz = projectAuthz;
    }

    /**
     * Use-case: store a binary artifact for a task.
     * Side effects: persists artifact metadata and writes bytes to storage adapter.
     */
    @Transactional
    public ArtifactRecord upload(String taskId, String name, String contentType, InputStream data) {
        requireTaskExists(taskId);
        ArtifactRecord record = artifactsPort.store(taskId, name, contentType, data);
        auditPort.append(taskId, actorOrSystem(), "artifact.upload", Map.of(
                "artifactId", record.artifactId(),
                "name", record.name(),
                "sha256", record.sha256(),
                "sizeBytes", record.sizeBytes()
        ));
        return record;
    }

    @Transactional(readOnly = true)
    public List<ArtifactRecord> list(String taskId) {
        requireTaskExists(taskId);
        return artifactsPort.listByTask(taskId);
    }

    /**
     * Use-case: download an artifact (authz default-deny).
     * Side effects: successful download is appended to audit chain.
     */
    @Transactional
    public ArtifactContent download(String taskId, String artifactId, String token) {
        return openWithSharedToken(taskId, artifactId, token, "artifact.download", "download forbidden");
    }

    /**
     * Inline preview of stored bytes (same shared-token gate as download).
     */
    @Transactional
    public ArtifactContent preview(String taskId, String artifactId, String token) {
        return openWithSharedToken(taskId, artifactId, token, "artifact.preview", "preview forbidden");
    }

    /**
     * Hosted-site reader.
     *
     * Authorization model:
     * - Authenticated users must still pass task membership ACL.
     * - Anonymous users may access only with a valid shared token.
     *
     * We intentionally surface unauthorized access as 404 to avoid artifact enumeration.
     */
    @Transactional(readOnly = true)
    public ArtifactContent openHostedSite(String taskId, String artifactId, String token) {
        assertHostedSiteAccess(taskId, artifactId, token);
        return artifactsPort.open(taskId, artifactId);
    }

    private ArtifactContent openWithSharedToken(
            String taskId,
            String artifactId,
            String token,
            String auditEventType,
            String forbiddenMessage
    ) {
        requireTaskExists(taskId);
        if (!downloadAuthzPort.canDownload(taskId, artifactId, token)) {
            throw new ArtifactForbiddenException(forbiddenMessage);
        }
        ArtifactContent content = artifactsPort.open(taskId, artifactId);
        auditPort.append(taskId, actorOrSystem(), auditEventType, Map.of(
                "artifactId", artifactId,
                "name", content.record().name(),
                "sha256", content.record().sha256(),
                "sizeBytes", content.record().sizeBytes()
        ));
        return content;
    }

    private String actorOrSystem() {
        String u = SecurityPrincipalUtils.currentUsernameOrNull();
        return u == null ? "operator" : u;
    }

    @Transactional(readOnly = true)
    public void assertHostedSiteAccess(String taskId, String artifactId, String token) {
        requireTaskExists(taskId);
        String username = SecurityPrincipalUtils.currentUsernameOrNull();
        if (username != null) {
            if (!projectAuthz.canAccessTask(taskId)) {
                throw new ArtifactNotFoundException("artifact not found");
            }
            return;
        }
        if (!downloadAuthzPort.canDownload(taskId, artifactId, token)) {
            throw new ArtifactNotFoundException("artifact not found");
        }
    }

    private void requireTaskExists(String taskId) {
        if (taskId == null || taskId.isBlank()) {
            throw new IllegalArgumentException("taskId is required");
        }
        if (!taskReadPort.exists(taskId)) {
            throw new TaskNotFoundException("task not found");
        }
    }
}

