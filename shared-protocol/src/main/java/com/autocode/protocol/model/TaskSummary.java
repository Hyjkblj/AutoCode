/**
 * Task summary view used for list/status operations and agent polling.
 */
package com.autocode.protocol.model;

import java.time.Instant;

public class TaskSummary {
    private String taskId;
    private String projectId;
    private String prompt;
    private String assistant;
    private String workspacePath;
    private String agentProfile;
    private String sessionKey;
    private TaskStatus status;
    private String assignedNodeId;
    private Instant createdAt;
    private Instant updatedAt;

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getAssistant() {
        return assistant;
    }

    public void setAssistant(String assistant) {
        this.assistant = assistant;
    }

    public String getWorkspacePath() {
        return workspacePath;
    }

    public void setWorkspacePath(String workspacePath) {
        this.workspacePath = workspacePath;
    }

    public String getAgentProfile() {
        return agentProfile;
    }

    public void setAgentProfile(String agentProfile) {
        this.agentProfile = agentProfile;
    }

    public String getSessionKey() {
        return sessionKey;
    }

    public void setSessionKey(String sessionKey) {
        this.sessionKey = sessionKey;
    }

    public TaskStatus getStatus() {
        return status;
    }

    public void setStatus(TaskStatus status) {
        this.status = status;
    }

    public String getAssignedNodeId() {
        return assignedNodeId;
    }

    public void setAssignedNodeId(String assignedNodeId) {
        this.assignedNodeId = assignedNodeId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
