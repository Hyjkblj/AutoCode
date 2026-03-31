package com.autocode.controlplane.artifacts.domain;

import java.time.Instant;

public record ArtifactRecord(
        String artifactId,
        String taskId,
        String name,
        String contentType,
        long sizeBytes,
        String sha256,
        Instant createdAt
) {
}

