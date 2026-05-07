package com.autocode.controlplane.artifacts.ports;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;

import java.io.InputStream;
import java.time.Instant;
import java.util.List;

public interface ArtifactsPort {
    ArtifactRecord store(String taskId, String name, String contentType, InputStream data);

    List<ArtifactRecord> listByTask(String taskId);

    ArtifactContent open(String taskId, String artifactId);

    /**
     * Delete an artifact's file from storage. Returns the storage path for cleanup.
     * The caller is responsible for deleting the DB record.
     */
    String deleteFile(String taskId, String artifactId);

    /**
     * Find artifacts created before the given cutoff time.
     */
    List<ArtifactRecord> findExpiredByAge(Instant cutoff);

    /**
     * Clean up stale .tmp files left by crashed store operations.
     * Returns the number of files cleaned.
     */
    int cleanStaleTmpFiles();
}

