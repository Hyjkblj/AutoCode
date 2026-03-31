/**
 * JPA entity for registered agent nodes and their heartbeat timestamps.
 */
package com.autocode.controlplane.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "agent_nodes")
public class AgentNodeEntity {
    @Id
    @Column(name = "node_id", nullable = false, length = 64)
    private String nodeId;

    @Column(name = "version", length = 64)
    private String version;

    @Column(name = "capabilities", columnDefinition = "TEXT")
    private String capabilities;

    @Column(name = "last_heartbeat_at")
    private Instant lastHeartbeatAt;

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

    public Instant getLastHeartbeatAt() {
        return lastHeartbeatAt;
    }

    public void setLastHeartbeatAt(Instant lastHeartbeatAt) {
        this.lastHeartbeatAt = lastHeartbeatAt;
    }
}
