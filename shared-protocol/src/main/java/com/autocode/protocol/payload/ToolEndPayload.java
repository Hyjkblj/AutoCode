package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TOOL_END}.
 */
public class ToolEndPayload {
    /**
     * Required. Tool name, for example {@code command.exec}.
     */
    private String tool;

    /**
     * Required. Suggested values: ok | timeout | error | denied.
     */
    private String status;

    /**
     * Optional. Process exit code when applicable.
     */
    private Integer exitCode;

    /**
     * Optional. Human-readable output snippet.
     */
    private String output;

    /**
     * Optional. Error description when status is not successful.
     */
    private String error;

    /**
     * Optional. Tool implementation version.
     */
    private String toolVersion;

    /**
     * Optional. Task trace id.
     */
    private String traceId;

    /**
     * Optional. Execution run id.
     */
    private String runId;

    /**
     * Optional. Approval correlation id when gated.
     */
    private String approvalId;

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
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

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
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
