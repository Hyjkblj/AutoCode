package com.autocode.artifact;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/**
 * JPA entity representing a stored artifact.
 * Maps to the {@code artifacts} table.
 *
 * Requirements: 14.1, 14.4
 */
@Entity
@Table(name = "artifacts")
public class ArtifactEntity {

    @Id
    @Column(name = "artifact_id", nullable = false, length = 64)
    private String artifactId;

    /** Owning task identifier — links artifact back to the generation task. */
    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    /** Human-readable file name (e.g. "backend.zip"). */
    @Column(name = "name", nullable = false, length = 256)
    private String name;

    /** MIME type of the stored artifact (e.g. "application/zip"). */
    @Column(name = "content_type", length = 128)
    private String contentType;

    /** Size of the stored file in bytes. */
    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;

    /** SHA-256 hex digest of the stored bytes for integrity verification. */
    @Column(name = "sha256", nullable = false, length = 64)
    private String sha256;

    /** Absolute path on the local filesystem where the bytes are stored. */
    @Column(name = "storage_path", nullable = false, length = 1024)
    private String storagePath;

    /** Generation timestamp — satisfies Requirement 14.4. */
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    // ---- Getters / Setters ----

    public String getArtifactId() { return artifactId; }
    public void setArtifactId(String artifactId) { this.artifactId = artifactId; }

    public String getTaskId() { return taskId; }
    public void setTaskId(String taskId) { this.taskId = taskId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getContentType() { return contentType; }
    public void setContentType(String contentType) { this.contentType = contentType; }

    public long getSizeBytes() { return sizeBytes; }
    public void setSizeBytes(long sizeBytes) { this.sizeBytes = sizeBytes; }

    public String getSha256() { return sha256; }
    public void setSha256(String sha256) { this.sha256 = sha256; }

    public String getStoragePath() { return storagePath; }
    public void setStoragePath(String storagePath) { this.storagePath = storagePath; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
