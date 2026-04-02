package com.autocode.agent.artifact;

import com.autocode.protocol.model.ArtifactMetadata;

import java.util.Locale;

/**
 * Maps local file naming to artifact {@code type} / MIME hints for uploads and {@code ARTIFACT_READY} {@code kind}.
 */
public final class LocalArtifactMapper {

    private LocalArtifactMapper() {
    }

    public static String guessMimeType(String fileName) {
        if (fileName == null) {
            return "application/octet-stream";
        }
        String n = fileName.toLowerCase(Locale.ROOT);
        if (n.endsWith(".zip")) {
            return "application/zip";
        }
        if (n.endsWith(".jar") || n.endsWith(".war")) {
            return "application/java-archive";
        }
        if (n.endsWith(".gz") || n.endsWith(".tgz")) {
            return "application/gzip";
        }
        if (n.endsWith(".json")) {
            return "application/json";
        }
        if (n.endsWith(".log") || n.endsWith(".txt")) {
            return "text/plain";
        }
        return "application/octet-stream";
    }

    /**
     * Artifact {@code type} string (schema: minLength 1). Aligns with common {@code kind} values where possible.
     */
    public static String inferArtifactType(String fileName) {
        if (fileName == null || fileName.isBlank()) {
            return "binary";
        }
        String n = fileName.toLowerCase(Locale.ROOT);
        if (n.endsWith(".zip") || n.endsWith(".jar") || n.endsWith(".war")) {
            return "zip";
        }
        if (n.endsWith(".log") || n.endsWith(".txt")) {
            return "log";
        }
        return "binary";
    }

    /**
     * Suggested {@code ARTIFACT_READY.payload.kind} from server-returned metadata (fallback: artifact type).
     */
    public static String inferKind(ArtifactMetadata metadata) {
        if (metadata == null) {
            return null;
        }
        String t = metadata.getType();
        if (t != null && !t.isBlank()) {
            return t.trim();
        }
        return null;
    }
}
