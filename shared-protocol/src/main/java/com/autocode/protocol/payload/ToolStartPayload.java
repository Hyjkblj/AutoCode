package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TOOL_START}.
 */
public class ToolStartPayload {
    /**
     * Required. Tool name, for example {@code command.exec}.
     */
    private String tool;

    /**
     * Optional. Suggested values: run_command, read_file, write_file.
     */
    private String action;

    /**
     * Optional. Human-readable command summary.
     */
    private String command;

    /**
     * Optional. Working directory reference.
     */
    private String cwd;

    /**
     * Optional. Normalized workspace reference (slash-normalized path or workspace URI).
     */
    private String workspaceRef;

    /**
     * Optional. Tool implementation version.
     */
    private String toolVersion;

    /**
     * Optional. Approval correlation id when gated.
     */
    private String approvalId;

    /**
     * Optional. Task trace id.
     */
    private String traceId;

    /**
     * Optional. Execution run id.
     */
    private String runId;

    /**
     * Optional. Routed intent skill id for orchestration diagnostics.
     */
    private String intentSkill;

    /**
     * Optional. Intent routing source for diagnostics.
     */
    private String intentRoute;

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
    }

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
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

    public String getToolVersion() {
        return toolVersion;
    }

    public void setToolVersion(String toolVersion) {
        this.toolVersion = toolVersion;
    }

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
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

    public String getIntentSkill() {
        return intentSkill;
    }

    public void setIntentSkill(String intentSkill) {
        this.intentSkill = intentSkill;
    }

    public String getIntentRoute() {
        return intentRoute;
    }

    public void setIntentRoute(String intentRoute) {
        this.intentRoute = intentRoute;
    }
}
