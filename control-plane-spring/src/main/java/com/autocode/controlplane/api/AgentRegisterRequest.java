/**
 * Agent registration request payload.
 */
package com.autocode.controlplane.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class AgentRegisterRequest {
    @NotBlank
    @Size(max = 64)
    private String nodeId;

    @Size(max = 64)
    private String version;

    @Size(max = 8192)
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
