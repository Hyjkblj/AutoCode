package com.autocode.approval.dto;

import com.autocode.protocol.model.ApprovalContext;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.List;

/**
 * DTO for creating an approval request.
 */
public class ApprovalRequestDto {

    @NotBlank(message = "Approval ID is required")
    private String approvalId;

    @NotBlank(message = "Task ID is required")
    private String taskId;

    private String traceId;
    private String runId;

    private ApprovalContext context;

    private String reason;
    private String action;
    private String tool;
    private String command;
    private String workspaceRef;
    private Integer timeoutSeconds;
    private Double riskScore;
    private List<String> requiredPolicies;

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

    public Integer getTimeoutSeconds() {
        return timeoutSeconds;
    }

    public void setTimeoutSeconds(Integer timeoutSeconds) {
        this.timeoutSeconds = timeoutSeconds;
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
}
