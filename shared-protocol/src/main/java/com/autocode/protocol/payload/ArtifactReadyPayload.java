package com.autocode.protocol.payload;

import com.autocode.protocol.model.ArtifactMetadata;

/**
 * Payload for {@code EventType.ARTIFACT_READY}.
 */
public class ArtifactReadyPayload {
    /**
     * Required.
     */
    private ArtifactMetadata artifact;

    /**
     * Optional. Suggested values: zip | spec | build-report | patch
     */
    private String kind;

    public ArtifactMetadata getArtifact() {
        return artifact;
    }

    public void setArtifact(ArtifactMetadata artifact) {
        this.artifact = artifact;
    }

    public String getKind() {
        return kind;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }
}

