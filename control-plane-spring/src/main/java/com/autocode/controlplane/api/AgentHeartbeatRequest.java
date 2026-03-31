/**
 * Agent heartbeat request payload.
 */
package com.autocode.controlplane.api;

import jakarta.validation.constraints.NotBlank;

public class AgentHeartbeatRequest {
    @NotBlank
    private String nodeId;

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }
}
