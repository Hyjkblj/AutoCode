package com.autocode.approval.entity;

import com.autocode.protocol.model.ApprovalDecision;
import jakarta.persistence.*;
import java.time.Instant;

/**
 * Entity representing an approval request for a high-risk task operation.
 * 
 * <p>Validates: Requirements 13.2 (RBAC), 13.3 (Audit Trail)
 */
@Entity
@Table(name = "approvals", indexes = {
    @Index(name = "idx_approvals_task_id", columnList = "task_id"),
    @Index(name = "idx_approvals_status", columnList = "decision"),
    @Index(name = "idx_approvals_created", columnList = "created_at")
})
public class ApprovalEntity {

    @Id
    @Column(name = "approval_id", length = 64, nullable = false)
    private String approvalId;

    @Column(name = "task_id", length = 64, nullable = false)
    private String taskId;

    @Column(name = "trace_id", length = 128)
    private String traceId;

    @Column(name = "run_id", length = 128)
    private String runId;

    @Column(name = "action", length = 128)
    private String action;

    @Column(name = "tool", length = 128)
    private String tool;

    @Column(name = "command", columnDefinition = "TEXT")
    private String command;

    @Column(name = "workspace_ref", length = 512)
    private String workspaceRef;

    @Column(name = "reason", columnDefinition = "TEXT")
    private String reason;

    @Column(name = "risk_score")
    private Double riskScore;

    @Column(name = "required_policies", columnDefinition = "TEXT")
    private String requiredPolicies; // JSON array stored as text

    @Column(name = "context_json", columnDefinition = "TEXT")
    private String contextJson; // ApprovalContext serialized as JSON

    @Enumerated(EnumType.STRING)
    @Column(name = "decision", length = 32, nullable = false)
    private ApprovalDecision decision = ApprovalDecision.PENDING;

    @Column(name = "decision_message", columnDefinition = "TEXT")
    private String decisionMessage;

    @Column(name = "decided_by", length = 128)
    private String decidedBy;

    @Column(name = "decided_at")
    private Instant decidedAt;

    @Column(name = "timeout_seconds")
    private Integer timeoutSeconds;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        Instant now = Instant.now();
        if (createdAt == null) {
            createdAt = now;
        }
        updatedAt = now;
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }

    // Getters and Setters

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }

    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
    }

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
    }

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
    }

    public String getCommand() {
        return command;
    }

    public void setCommand(String command) {
        this.command = command;
    }

    public String getWorkspaceRef() {
        return workspaceRef;
    }

    public void setWorkspaceRef(String workspaceRef) {
        this.workspaceRef = workspaceRef;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public Double getRiskScore() {
        return riskScore;
    }

    public void setRiskScore(Double riskScore) {
        this.riskScore = riskScore;
    }

    public String getRequiredPolicies() {
        return requiredPolicies;
    }

    public void setRequiredPolicies(String requiredPolicies) {
        this.requiredPolicies = requiredPolicies;
    }

    public String getContextJson() {
        return contextJson;
    }

    public void setContextJson(String contextJson) {
        this.contextJson = contextJson;
    }

    public ApprovalDecision getDecision() {
        return decision;
    }

    public void setDecision(ApprovalDecision decision) {
        this.decision = decision;
    }

    public String getDecisionMessage() {
        return decisionMessage;
    }

    public void setDecisionMessage(String decisionMessage) {
        this.decisionMessage = decisionMessage;
    }

    public String getDecidedBy() {
        return decidedBy;
    }

    public void setDecidedBy(String decidedBy) {
        this.decidedBy = decidedBy;
    }

    public Instant getDecidedAt() {
        return decidedAt;
    }

    public void setDecidedAt(Instant decidedAt) {
        this.decidedAt = decidedAt;
    }

    public Integer getTimeoutSeconds() {
        return timeoutSeconds;
    }

    public void setTimeoutSeconds(Integer timeoutSeconds) {
        this.timeoutSeconds = timeoutSeconds;
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
