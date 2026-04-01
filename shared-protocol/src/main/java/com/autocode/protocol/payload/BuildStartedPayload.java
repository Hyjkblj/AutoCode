package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.BUILD_STARTED}.
 */
public class BuildStartedPayload {
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

