package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TASK_STARTED}.
 */
public class TaskStartedPayload {
    /**
     * Required. Node that claimed execution lease.
     */
    private String nodeId;

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }
}
