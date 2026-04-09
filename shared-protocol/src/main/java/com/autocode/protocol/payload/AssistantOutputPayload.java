package com.autocode.protocol.payload;

import java.util.ArrayList;
import java.util.List;

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
     * Optional. Normalized intent category (e.g. code_change/deploy/test/analyze).
     */
    private String intent;

    /**
     * Optional. Model confidence in [0,1].
     */
    private Double confidence;

    /**
     * Optional. Reason text from intent classification.
     */
    private String reason;

    /**
     * Optional. Indicates the producer fell back from LLM to rule/template behavior.
     */
    private Boolean llmFallback;

    /**
     * Optional. Review risk level from ReviewerAgent (high/medium/low).
     */
    private String riskLevel;

    /**
     * Optional. Human-readable review issues.
     */
    private List<String> issues = new ArrayList<>();

    /**
     * Optional. Review summary.
     */
    private String summary;

    /**
     * Optional. Current fix-loop attempt (1-based).
     */
    private Integer attempt;

    /**
     * Optional. Maximum fix-loop attempts allowed.
     */
    private Integer maxAttempts;

    /**
     * Optional. Latest test error excerpt used by fix-loop prompts.
     */
    private String lastTestError;

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

    public String getIntent() {
        return intent;
    }

    public void setIntent(String intent) {
        this.intent = intent;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public Boolean getLlmFallback() {
        return llmFallback;
    }

    public void setLlmFallback(Boolean llmFallback) {
        this.llmFallback = llmFallback;
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
