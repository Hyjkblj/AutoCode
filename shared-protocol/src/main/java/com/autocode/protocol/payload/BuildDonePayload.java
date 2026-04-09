package com.autocode.protocol.payload;

import com.autocode.protocol.model.ArtifactMetadata;

/**
 * Payload for {@code EventType.BUILD_DONE}.
 */
public class BuildDonePayload {
    /**
     * Optional. End-to-end trace correlation id.
     */
    private String traceId;
    /**
     * Optional. Runtime execution correlation id.
     */
    private String runId;
    private String buildId;
    /**
     * Suggested values: success | failed
     */
    private String status;
    private Long durationMs;
    /**
     * Optional. Artifact reference for build report (e.g. build-report.json).
     */
    private ArtifactMetadata reportArtifact;

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

    public String getBuildId() {
        return buildId;
    }

    public void setBuildId(String buildId) {
        this.buildId = buildId;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Long getDurationMs() {
        return durationMs;
    }

    public void setDurationMs(Long durationMs) {
        this.durationMs = durationMs;
    }

    public ArtifactMetadata getReportArtifact() {
        return reportArtifact;
    }

    public void setReportArtifact(ArtifactMetadata reportArtifact) {
        this.reportArtifact = reportArtifact;
    }
}

