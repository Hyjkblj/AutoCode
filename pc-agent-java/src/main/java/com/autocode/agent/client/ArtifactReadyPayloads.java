/**
 * Builds artifact-ready style payload maps from {@link ArtifactMetadata}.
 *
 * Note: the exact event type / schema may evolve with shared-protocol; keep this helper
 * compatible with the current {@link ArtifactMetadata} fields.
 */
package com.autocode.agent.client;

import com.autocode.protocol.model.ArtifactMetadata;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class ArtifactReadyPayloads {

    private ArtifactReadyPayloads() {
    }

    /**
     * @throws IllegalArgumentException when required fields for schema validation are missing
     */
    public static Map<String, Object> fromMetadata(ArtifactMetadata metadata) {
        return fromMetadata(metadata, null);
    }

    /**
     * Builds payload compatible with shared-protocol {@code ARTIFACT_READY v1} schema:
     * <pre>
     *   { "artifact": { ... }, "kind": "zip" }
     * </pre>
     *
     * @param kind optional hint for UI; suggested values: zip | spec | build-report | patch
     */
    public static Map<String, Object> fromMetadata(ArtifactMetadata metadata, String kind) {
        if (metadata == null) {
            throw new IllegalArgumentException("metadata is required");
        }
        String artifactId = trimToNull(metadata.getArtifactId());
        if (artifactId == null) {
            throw new IllegalArgumentException("artifactId is required");
        }

        String type = trimToNull(metadata.getType());
        if (type == null) {
            throw new IllegalArgumentException("type is required for artifact payload");
        }

        Long size = metadata.getSize();
        if (size != null && size < 0) {
            throw new IllegalArgumentException("size must be >= 0 when provided");
        }

        HashMap<String, Object> artifact = new HashMap<>();
        artifact.put("artifactId", artifactId);
        artifact.put("type", type);

        String hash = trimToNull(metadata.getHash());
        if (hash != null) {
            artifact.put("hash", hash);
        }
        if (size != null) {
            artifact.put("size", size);
        }
        String mime = trimToNull(metadata.getMime());
        if (mime != null) {
            artifact.put("mime", mime);
        }
        putOptionalString(artifact, "name", metadata.getName());
        putOptionalString(artifact, "downloadUrl", metadata.getDownloadUrl());
        putOptionalString(artifact, "entryPath", metadata.getEntryPath());

        ArtifactMetadata.BuildDescriptor build = metadata.getBuild();
        if (build != null) {
            String command = trimToNull(build.getCommand());
            if (command == null) {
                throw new IllegalArgumentException("build.command is required when build is set");
            }
            HashMap<String, Object> buildMap = new HashMap<>();
            buildMap.put("command", command);
            putOptionalString(buildMap, "workingDir", build.getWorkingDir());
            artifact.put("build", buildMap);
        }

        ArtifactMetadata.RunDescriptor run = metadata.getRun();
        if (run != null) {
            HashMap<String, Object> runMap = new HashMap<>();
            putOptionalString(runMap, "command", run.getCommand());
            List<String> hints = normalizeHints(run.getHints());
            if (!hints.isEmpty()) {
                runMap.put("hints", hints);
            }
            if (!runMap.isEmpty()) {
                artifact.put("run", runMap);
            }
        }

        HashMap<String, Object> payload = new HashMap<>();
        payload.put("artifact", artifact);

        String k = (kind == null || kind.isBlank()) ? null : kind.trim();
        if (k != null) {
            payload.put("kind", k);
        }

        return payload;
    }

    private static List<String> normalizeHints(List<String> rawHints) {
        if (rawHints == null || rawHints.isEmpty()) {
            return List.of();
        }
        ArrayList<String> hints = new ArrayList<>();
        for (String raw : rawHints) {
            String hint = trimToNull(raw);
            if (hint != null && !hints.contains(hint)) {
                hints.add(hint);
            }
        }
        return hints;
    }

    private static void putOptionalString(Map<String, Object> target, String key, String value) {
        String normalized = trimToNull(value);
        if (normalized != null) {
            target.put(key, normalized);
        }
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
