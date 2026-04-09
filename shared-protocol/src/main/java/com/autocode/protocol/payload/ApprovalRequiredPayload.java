package com.autocode.protocol.payload;

import com.autocode.protocol.model.ApprovalContext;

import java.util.List;

/**
 * Payload for {@code EventType.APPROVAL_REQUIRED}.
 */
public class ApprovalRequiredPayload {
    /**
     * Required. Correlation id for later {@code APPROVAL_RESULT}.
     */
    private String approvalId;
    /**
     * Required. Strong-binding context.
     */
    private ApprovalContext context;
    /**
     * Optional. Human-readable reason.
     */
    private String reason;
    /**
     * Optional. Routed action for approval gate.
     */
    private String action;
    /**
     * Optional. Tool name that will execute after approval.
     */
    private String tool;
    /**
     * Optional. Human-readable command preview.
     */
    private String command;
    /**
     * Optional. Runner working directory.
     */
    private String cwd;
    /**
     * Optional. Normalized workspace reference.
     */
    private String workspaceRef;
    /**
     * Optional. Approval timeout in seconds.
     */
    private Integer approvalTimeoutSeconds;
    /**
     * Optional. Tool/policy risk score in range [0,1].
     */
    private Double riskScore;
    /**
     * Optional. Required policy identifiers for approval.
     */
    private List<String> requiredPolicies;
    /**
     * Optional. Tool manifest version.
     */
    private String toolVersion;

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
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

    public String getCwd() {
        return cwd;
    }

    public void setCwd(String cwd) {
        this.cwd = cwd;
    }

    public String getWorkspaceRef() {
        return workspaceRef;
    }

    public void setWorkspaceRef(String workspaceRef) {
        this.workspaceRef = workspaceRef;
    }

    public Integer getApprovalTimeoutSeconds() {
        return approvalTimeoutSeconds;
    }

    public void setApprovalTimeoutSeconds(Integer approvalTimeoutSeconds) {
        this.approvalTimeoutSeconds = approvalTimeoutSeconds;
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

    public String getToolVersion() {
        return toolVersion;
    }

    public void setToolVersion(String toolVersion) {
        this.toolVersion = toolVersion;
    }
}

