package com.autocode.protocol.model;

import java.util.List;

/**
 * Standalone artifact manifest (e.g. bundled with a task export or stored as JSON).
 * Schema: {@code schema/manifest/v1/artifact_manifest.v1.schema.json}.
 */
public class ArtifactManifest {
    private int schemaVersion = 1;
    private List<ArtifactMetadata> artifacts;
    private String defaultArtifactId;

    public int getSchemaVersion() {
        return schemaVersion;
    }

    public void setSchemaVersion(int schemaVersion) {
        this.schemaVersion = schemaVersion;
    }

    public List<ArtifactMetadata> getArtifacts() {
        return artifacts;
    }

    public void setArtifacts(List<ArtifactMetadata> artifacts) {
        this.artifacts = artifacts;
    }

    public String getDefaultArtifactId() {
        return defaultArtifactId;
    }

    public void setDefaultArtifactId(String defaultArtifactId) {
        this.defaultArtifactId = defaultArtifactId;
    }
}
