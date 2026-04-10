package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.HEARTBEAT}.
 */
public class HeartbeatPayload {
    /**
     * Optional. Node identifier when heartbeat is emitted in task streams.
     */
    private String nodeId;

    /**
     * Optional. Human-readable status (e.g. alive).
     */
    private String status;

    /**
     * Optional. Milliseconds since process start.
     */
    private Long uptimeMs;

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Long getUptimeMs() {
        return uptimeMs;
    }

    public void setUptimeMs(Long uptimeMs) {
        this.uptimeMs = uptimeMs;
    }
}
