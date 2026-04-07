package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.ASSISTANT_OUTPUT}.
 */
public class AssistantOutputPayload {
    /**
     * Required. Main assistant text shown to users.
     */
    private String message;

    /**
     * Optional. Producer stage marker (e.g. IntentAgent/PlannerAgent/ExecTool).
     */
    private String stage;

    /**
     * Optional. Structured code or command hint.
     */
    private String command;

    /**
     * Optional. Correlation id for distributed tracing.
     */
    private String traceId;

    /**
     * Optional. Correlation id for one execution run.
     */
    private String runId;

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getStage() {
        return stage;
    }

    public void setStage(String stage) {
        this.stage = stage;
    }

    public String getCommand() {
        return command;
    }

    public void setCommand(String command) {
        this.command = command;
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
