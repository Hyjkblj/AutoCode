package com.autocode.protocol.payload;

import com.autocode.protocol.model.ArtifactMetadata;

/**
 * Payload for {@code EventType.SPEC_PROPOSED}.
 *
 * Represents a structured reference to a generated spec (e.g. spec.json) plus optional summary metadata.
 */
public class SpecProposedPayload {
    /**
     * Required. Artifact reference for the spec content.
     */
    private ArtifactMetadata artifact;

    /**
     * Optional. Logical path inside workspace (e.g. "spec.json").
     */
    private String path;

    /**
     * Optional. Human-readable structured summary (kept short; clients may display it).
     */
    private String summary;

    /**
     * Optional. Spec schema version (e.g. "v1").
     */
    private String schemaVersion;

    public ArtifactMetadata getArtifact() {
        return artifact;
    }

    public void setArtifact(ArtifactMetadata artifact) {
        this.artifact = artifact;
    }

    public String getPath() {
        return path;
    }

    public void setPath(String path) {
        this.path = path;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public String getSchemaVersion() {
        return schemaVersion;
    }

    public void setSchemaVersion(String schemaVersion) {
        this.schemaVersion = schemaVersion;
    }
}

