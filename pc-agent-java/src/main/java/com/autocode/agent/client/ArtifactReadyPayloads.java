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
        if (metadata == null) {
            throw new IllegalArgumentException("metadata is required");
        }
        String artifactId = metadata.getArtifactId();
        if (artifactId == null || artifactId.isBlank()) {
            throw new IllegalArgumentException("artifactId is required");
        }
        Long size = metadata.getSize();
        if (size == null || size < 0) {
            throw new IllegalArgumentException("size is required and must be >= 0");
        }
        String hash = metadata.getHash();
        if (hash == null || hash.isBlank()) {
            throw new IllegalArgumentException("hash is required for artifact payload");
        }
        HashMap<String, Object> payload = new HashMap<>();
        payload.put("artifactId", artifactId);
        payload.put("size", size);
        payload.put("hash", hash);
        if (metadata.getMime() != null && !metadata.getMime().isBlank()) {
            payload.put("mime", metadata.getMime());
        }
        if (metadata.getType() != null && !metadata.getType().isBlank()) {
            payload.put("type", metadata.getType());
        }
        return payload;
    }
}
