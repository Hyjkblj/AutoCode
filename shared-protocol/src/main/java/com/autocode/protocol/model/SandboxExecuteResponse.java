package com.autocode.protocol.model;

/**
 * Response body for the localhost sandbox execute endpoint.
 */
public class SandboxExecuteResponse {
    private boolean ok;
    private String status;
    private Integer exitCode;
    private String output;
    private boolean retryable;
    private String reason;
    private String tool;
    private String toolVersion;
    private String traceId;
    private String runId;
    private String approvalId;

    public static SandboxExecuteResponse success(
            String status,
            Integer exitCode,
            String output,
            boolean retryable,
            String tool,
            String toolVersion,
            String traceId,
            String runId) {
        SandboxExecuteResponse response = new SandboxExecuteResponse();
        response.ok = true;
        response.status = status;
        response.exitCode = exitCode;
        response.output = output;
        response.retryable = retryable;
        response.tool = tool;
        response.toolVersion = toolVersion;
        response.traceId = traceId;
        response.runId = runId;
        return response;
    }

    public static SandboxExecuteResponse failure(
            String status,
            String reason,
            boolean retryable,
            String tool,
            String toolVersion,
            String traceId,
            String runId,
            String approvalId) {
        SandboxExecuteResponse response = new SandboxExecuteResponse();
        response.ok = false;
        response.status = status;
        response.reason = reason;
        response.retryable = retryable;
        response.tool = tool;
        response.toolVersion = toolVersion;
        response.traceId = traceId;
        response.runId = runId;
        response.approvalId = approvalId;
        return response;
    }

    public boolean isOk() {
        return ok;
    }

    public void setOk(boolean ok) {
        this.ok = ok;
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

    public String getOutput() {
        return output;
    }

    public void setOutput(String output) {
        this.output = output;
    }

    public boolean isRetryable() {
        return retryable;
    }

    public void setRetryable(boolean retryable) {
        this.retryable = retryable;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
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

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }
}
