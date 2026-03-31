/**
 * JPA entity representing a task and its current state in the control plane.
 */
package com.autocode.controlplane.persistence.entity;

import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.TaskStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "tasks")
public class TaskEntity {
    @Id
    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    @Column(name = "session_id", nullable = false, length = 64)
    private String sessionId;

    @Column(name = "project_id", nullable = false, length = 128)
    private String projectId;

    @Column(name = "prompt", nullable = false, columnDefinition = "TEXT")
    private String prompt;

    @Column(name = "assistant", nullable = false, length = 64)
    private String assistant;

    @Column(name = "input_mode", nullable = false, length = 64)
    private String inputMode;

    @Column(name = "risk_policy", nullable = false, length = 64)
    private String riskPolicy;

    @Column(name = "workspace_path", length = 512)
    private String workspacePath;

    @Column(name = "agent_profile", length = 32)
    private String agentProfile;

    @Column(name = "session_key", length = 128)
    private String sessionKey;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private TaskStatus status;

    @Column(name = "assigned_node_id", length = 64)
    private String assignedNodeId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "leased_at")
    private Instant leasedAt;

    @Column(name = "lease_expires_at")
    private Instant leaseExpiresAt;

    @Column(name = "retry_count", nullable = false)
    private int retryCount;

    @Column(name = "next_run_at")
    private Instant nextRunAt;

    @Column(name = "next_seq", nullable = false)
    private long nextSeq;

    @Column(name = "approval_id", length = 64)
    private String approvalId;

    @Enumerated(EnumType.STRING)
    @Column(name = "approval_decision", nullable = false, length = 32)
    private ApprovalDecision approvalDecision;

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
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

    public String getInputMode() {
        return inputMode;
    }

    public void setInputMode(String inputMode) {
        this.inputMode = inputMode;
    }

    public String getRiskPolicy() {
        return riskPolicy;
    }

    public void setRiskPolicy(String riskPolicy) {
        this.riskPolicy = riskPolicy;
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

    public Instant getLeasedAt() {
        return leasedAt;
    }

    public void setLeasedAt(Instant leasedAt) {
        this.leasedAt = leasedAt;
    }

    public Instant getLeaseExpiresAt() {
        return leaseExpiresAt;
    }

    public void setLeaseExpiresAt(Instant leaseExpiresAt) {
        this.leaseExpiresAt = leaseExpiresAt;
    }

    public int getRetryCount() {
        return retryCount;
    }

    public void setRetryCount(int retryCount) {
        this.retryCount = retryCount;
    }

    public Instant getNextRunAt() {
        return nextRunAt;
    }

    public void setNextRunAt(Instant nextRunAt) {
        this.nextRunAt = nextRunAt;
    }

    public long getNextSeq() {
        return nextSeq;
    }

    public void setNextSeq(long nextSeq) {
        this.nextSeq = nextSeq;
    }

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }

    public ApprovalDecision getApprovalDecision() {
        return approvalDecision;
    }

    public void setApprovalDecision(ApprovalDecision approvalDecision) {
        this.approvalDecision = approvalDecision;
    }
}
