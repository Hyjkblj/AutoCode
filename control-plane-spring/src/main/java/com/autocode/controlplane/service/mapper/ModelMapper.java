/**
 * Maps persistence entities to protocol-facing models.
 */
package com.autocode.controlplane.service.mapper;

import com.autocode.controlplane.model.AgentNode;
import com.autocode.controlplane.persistence.entity.AgentNodeEntity;
import com.autocode.controlplane.persistence.entity.TaskEntity;
import com.autocode.protocol.model.TaskSummary;
import org.springframework.stereotype.Component;

@Component
public class ModelMapper {

    public TaskSummary toSummary(TaskEntity task) {
        TaskSummary summary = new TaskSummary();
        summary.setTaskId(task.getTaskId());
        summary.setProjectId(task.getProjectId());
        summary.setPrompt(task.getPrompt());
        summary.setAssistant(task.getAssistant());
        summary.setWorkspacePath(task.getWorkspacePath());
        summary.setAgentProfile(task.getAgentProfile());
        summary.setSessionKey(task.getSessionKey());
        summary.setStatus(task.getStatus());
        summary.setAssignedNodeId(task.getAssignedNodeId());
        summary.setCreatedAt(task.getCreatedAt());
        summary.setUpdatedAt(task.getUpdatedAt());
        return summary;
    }

    public AgentNode toAgentNode(AgentNodeEntity entity, boolean online) {
        AgentNode node = new AgentNode();
        node.setNodeId(entity.getNodeId());
        node.setVersion(entity.getVersion());
        node.setCapabilities(entity.getCapabilities());
        node.setLastHeartbeatAt(entity.getLastHeartbeatAt());
        node.setOnline(online);
        return node;
    }
}
