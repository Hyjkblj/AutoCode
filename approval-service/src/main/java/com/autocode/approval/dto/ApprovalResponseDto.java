package com.autocode.approval.dto;

import com.autocode.protocol.model.ApprovalContext;
import com.autocode.protocol.model.ApprovalDecision;

import java.time.Instant;
import java.util.List;

/**
 * DTO for approval response.
 */
public class ApprovalResponseDto {

    private String approvalId;
    private String taskId;
    private String traceId;
    private String runId;
    private ApprovalContext context;
    private String reason;
    private String action;
    private String tool;
    private String command;
    private String workspaceRef;
    private Double riskScore;
    private List<String> requiredPolicies;
    private ApprovalDecision decision;
    private String decisionMessage;
    private String decidedBy;
    private Instant decidedAt;
    private Integer timeoutSeconds;
    private Instant createdAt;
    private Instant updatedAt;

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

    public ApprovalContext getContext() {
        return context;
    }

    public void setContext(ApprovalContext context) {
        this.context = context;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
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

    public Double getRiskScore() {
        return riskScore;
    }

    public void setRiskScore(Double riskScore) {
        this.riskScore = riskScore;
    }

    public List<String> getRequiredPolicies() {
        return requiredPolicies;
    }

    public void setRequiredPolicies(List<String> requiredPolicies) {
        this.requiredPolicies = requiredPolicies;
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
