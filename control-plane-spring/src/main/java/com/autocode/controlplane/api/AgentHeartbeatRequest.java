/**
 * Agent heartbeat request payload.
 */
package com.autocode.controlplane.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class AgentHeartbeatRequest {
    @NotBlank
    @Size(max = 64)
    private String nodeId;

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }
}
