package com.autocode.protocol.payload;

import java.util.ArrayList;
import java.util.List;

/**
 * Payload for {@code EventType.TASK_FAILED}.
 */
public class TaskFailedPayload {
    /**
     * Required. Machine-readable failure reason.
     */
    private String reason;

    /**
     * Optional. Human-readable detail.
     */
    private String detail;

    /**
     * Optional. Plan name selected by orchestrator.
     */
    private String planName;

    /**
     * Optional. Producer-specific machine-readable error code.
     */
    private String errorCode;

    /**
     * Optional. Failure status from tool/sandbox layer.
     */
    private String status;

    /**
     * Optional. Process exit code when command execution fails.
     */
    private Integer exitCode;

    /**
     * Optional. Retry hint propagated by runner.
     */
    private Boolean retryable;

    /**
     * Optional. Policy decision explanation.
     */
    private String policyReason;

    /**
     * Optional. Related tool name.
     */
    private String tool;

    /**
     * Optional. Working directory context.
     */
    private String cwd;

    /**
     * Optional. Correlation id for distributed tracing.
     */
    private String traceId;

    /**
     * Optional. Correlation id for one execution run.
     */
    private String runId;

    /**
     * Optional. Current fix-loop attempt (1-based).
     */
    private Integer attempt;

    /**
     * Optional. Maximum fix-loop attempts allowed.
     */
    private Integer maxAttempts;

    /**
     * Optional. Latest test failure text for diagnostics.
     */
    private String lastTestError;

    /**
     * Optional. Review risk level (high/medium/low).
     */
    private String riskLevel;

    /**
     * Optional. Human-readable issue summaries from reviewer stage.
     */
    private List<String> issues = new ArrayList<>();

    /**
     * Optional. Review/failure summary text.
     */
    private String summary;

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public String getDetail() {
        return detail;
    }

    public void setDetail(String detail) {
        this.detail = detail;
    }

    public String getPlanName() {
        return planName;
    }

    public void setPlanName(String planName) {
        this.planName = planName;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(String errorCode) {
        this.errorCode = errorCode;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Integer getExitCode() {
        return exitCode;
    }

    public void setExitCode(Integer exitCode) {
        this.exitCode = exitCode;
    }

    public Boolean getRetryable() {
        return retryable;
    }

    public void setRetryable(Boolean retryable) {
        this.retryable = retryable;
    }

    public String getPolicyReason() {
        return policyReason;
    }

    public void setPolicyReason(String policyReason) {
        this.policyReason = policyReason;
    }

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
    }

    public String getCwd() {
        return cwd;
    }

    public void setCwd(String cwd) {
        this.cwd = cwd;
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

    public Integer getAttempt() {
        return attempt;
    }

    public void setAttempt(Integer attempt) {
        this.attempt = attempt;
    }

    public Integer getMaxAttempts() {
        return maxAttempts;
    }

    public void setMaxAttempts(Integer maxAttempts) {
        this.maxAttempts = maxAttempts;
    }

    public String getLastTestError() {
        return lastTestError;
    }

    public void setLastTestError(String lastTestError) {
        this.lastTestError = lastTestError;
    }

    public String getRiskLevel() {
        return riskLevel;
    }

    public void setRiskLevel(String riskLevel) {
        this.riskLevel = riskLevel;
    }

    public List<String> getIssues() {
        return issues;
    }

    public void setIssues(List<String> issues) {
        this.issues = issues;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }
}
