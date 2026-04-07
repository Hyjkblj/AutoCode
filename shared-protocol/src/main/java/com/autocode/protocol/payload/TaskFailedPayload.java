package com.autocode.protocol.payload;

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
}
