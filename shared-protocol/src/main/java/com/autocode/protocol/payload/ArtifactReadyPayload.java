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
     * Optional. Requested generation target (MVP: web).
     */
    private String target;

    /**
     * Optional. Selected template identifier.
     */
    private String templateId;

    /**
     * Optional. Requested export mode (e.g. zip).
     */
    private String exportMode;

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

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public String getTemplateId() {
        return templateId;
    }

    public void setTemplateId(String templateId) {
        this.templateId = templateId;
    }

    public String getExportMode() {
        return exportMode;
    }

    public void setExportMode(String exportMode) {
        this.exportMode = exportMode;
    }

    public String getKind() {
        return kind;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }
}

