package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.BUILD_LOG}.
 */
public class BuildLogPayload {
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
     * Suggested values: debug | info | warn | error
     */
    private String level;
    private String message;

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

    public String getLevel() {
        return level;
    }

    public void setLevel(String level) {
        this.level = level;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}

