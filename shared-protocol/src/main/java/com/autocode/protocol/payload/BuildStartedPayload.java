package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.BUILD_STARTED}.
 */
public class BuildStartedPayload {
    /**
     * Optional. End-to-end trace correlation id.
     */
    private String traceId;

    /**
     * Optional. Runtime execution correlation id.
     */
    private String runId;

    /**
     * Optional. Producer-generated build id for correlating logs.
     */
    private String buildId;

    /**
     * Optional. Suggested values: build.run | publish.run
     */
    private String tool;

    /**
     * Optional. Human-readable build target (e.g. "web", "miniapp").
     */
    private String target;

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

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }
}

