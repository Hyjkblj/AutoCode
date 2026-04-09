package com.autocode.protocol.payload;

import com.autocode.protocol.model.ArtifactMetadata;

/**
 * Payload for {@code EventType.SPEC_PROPOSED}.
 *
 * Represents a structured reference to a generated spec (e.g. spec.json) plus optional summary metadata.
 */
public class SpecProposedPayload {
    /**
     * Optional. End-to-end trace correlation id.
     */
    private String traceId;

    /**
     * Optional. Runtime execution correlation id.
     */
    private String runId;

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

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
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
