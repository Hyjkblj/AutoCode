/**
 * Agent registration request payload.
 */
package com.autocode.controlplane.api;

import jakarta.validation.constraints.NotBlank;

public class AgentRegisterRequest {
    @NotBlank
    private String nodeId;

    private String version;
    private String capabilities;

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }

    public String getCapabilities() {
        return capabilities;
    }

    public void setCapabilities(String capabilities) {
        this.capabilities = capabilities;
    }
}
