package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TASK_DONE}.
 */
public class TaskDonePayload {
    /**
     * Required. Suggested values: success | executed | coded_reviewed_tested | planned.
     */
    private String result;

    /**
     * Optional. Optional status detail from orchestrators/runners.
     */
    private String status;

    /**
     * Optional. Tool name for task completion summary.
     */
    private String tool;

    /**
     * Optional. Tool implementation version.
     */
    private String toolVersion;

    /**
     * Optional. Process exit code when completion comes from command execution.
     */
    private Integer exitCode;

    /**
     * Optional. Retry hint propagated by runner.
     */
    private Boolean retryable;

    /**
     * Optional. Human-readable output snippet.
     */
    private String output;

    /**
     * Optional. Correlation id for distributed tracing.
     */
    private String traceId;

    /**
     * Optional. Correlation id for one execution run.
     */
    private String runId;

    public String getResult() {
        return result;
    }

    public void setResult(String result) {
        this.result = result;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
    }

    public String getToolVersion() {
        return toolVersion;
    }

    public void setToolVersion(String toolVersion) {
        this.toolVersion = toolVersion;
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

    public String getOutput() {
        return output;
    }

    public void setOutput(String output) {
        this.output = output;
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
