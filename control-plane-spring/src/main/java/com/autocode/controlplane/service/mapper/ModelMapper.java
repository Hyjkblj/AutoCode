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
        // Backward/forward compatible with shared-protocol: these fields may not exist in older versions.
        invokeSetterIfPresent(summary, "setWorkspacePath", String.class, task.getWorkspacePath());
        invokeSetterIfPresent(summary, "setAgentProfile", String.class, task.getAgentProfile());
        invokeSetterIfPresent(summary, "setSessionId", String.class, task.getSessionId());
        invokeSetterIfPresent(summary, "setSessionKey", String.class, task.getSessionKey());
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

    private static <T, V> void invokeSetterIfPresent(T target, String setterName, Class<V> argType, V value) {
        try {
            target.getClass().getMethod(setterName, argType).invoke(target, value);
        } catch (NoSuchMethodException ignored) {
            // shared-protocol older version: field not present
        } catch (Exception e) {
            throw new IllegalStateException("Failed to invoke " + setterName, e);
        }
    }
}
