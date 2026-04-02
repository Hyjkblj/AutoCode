/**
 * Builds artifact-ready style payload maps from {@link ArtifactMetadata}.
 *
 * Note: the exact event type / schema may evolve with shared-protocol; keep this helper
 * compatible with the current {@link ArtifactMetadata} fields.
 */
package com.autocode.agent.client;

import com.autocode.protocol.model.ArtifactMetadata;

import java.util.HashMap;
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
        String artifactId = metadata.getArtifactId();
        if (artifactId == null || artifactId.isBlank()) {
            throw new IllegalArgumentException("artifactId is required");
        }

        String type = metadata.getType();
        if (type == null || type.isBlank()) {
            throw new IllegalArgumentException("type is required for artifact payload");
        }

        Long size = metadata.getSize();
        if (size != null && size < 0) {
            throw new IllegalArgumentException("size must be >= 0 when provided");
        }

        HashMap<String, Object> artifact = new HashMap<>();
        artifact.put("artifactId", artifactId);
        artifact.put("type", type);

        String hash = metadata.getHash();
        if (hash != null && !hash.isBlank()) {
            artifact.put("hash", hash);
        }
        if (size != null) {
            artifact.put("size", size);
        }
        if (metadata.getMime() != null && !metadata.getMime().isBlank()) {
            artifact.put("mime", metadata.getMime());
        }

        HashMap<String, Object> payload = new HashMap<>();
        payload.put("artifact", artifact);

        String k = (kind == null || kind.isBlank()) ? null : kind.trim();
        if (k != null) {
            payload.put("kind", k);
        }

        return payload;
    }
}
