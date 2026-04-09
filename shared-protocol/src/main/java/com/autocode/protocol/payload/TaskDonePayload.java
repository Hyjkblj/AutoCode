package com.autocode.protocol.payload;

import java.util.ArrayList;
import java.util.List;

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
     * Optional. Normalized intent category (e.g. code_change/deploy/test/analyze).
     */
    private String intent;

    /**
     * Optional. Plan name selected by orchestrator.
     */
    private String planName;

    /**
     * Optional. Planned step descriptions.
     */
    private List<String> steps = new ArrayList<>();

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
     * Optional. Code-review decision summary for code_change pipelines.
     */
    private Boolean reviewApproved;

    /**
     * Optional. Code-review summary for code_change pipelines.
     */
    private String reviewSummary;

    /**
     * Optional. Tester status for code_change pipelines.
     */
    private String testStatus;

    /**
     * Optional. Total test attempts performed.
     */
    private Integer testAttempts;

    /**
     * Optional. Total retry count used by tester.
     */
    private Integer testRetries;

    /**
     * Optional. Successful fix-loop attempt index (1-based).
     */
    private Integer attempt;

    /**
     * Optional. Maximum fix-loop attempts allowed.
     */
    private Integer maxAttempts;

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

    public String getIntent() {
        return intent;
    }

    public void setIntent(String intent) {
        this.intent = intent;
    }

    public String getPlanName() {
        return planName;
    }

    public void setPlanName(String planName) {
        this.planName = planName;
    }

    public List<String> getSteps() {
        return steps;
    }

    public void setSteps(List<String> steps) {
        this.steps = steps;
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

    public Boolean getReviewApproved() {
        return reviewApproved;
    }

    public void setReviewApproved(Boolean reviewApproved) {
        this.reviewApproved = reviewApproved;
    }

    public String getReviewSummary() {
        return reviewSummary;
    }

    public void setReviewSummary(String reviewSummary) {
        this.reviewSummary = reviewSummary;
    }

    public String getTestStatus() {
        return testStatus;
    }

    public void setTestStatus(String testStatus) {
        this.testStatus = testStatus;
    }

    public Integer getTestAttempts() {
        return testAttempts;
    }

    public void setTestAttempts(Integer testAttempts) {
        this.testAttempts = testAttempts;
    }

    public Integer getTestRetries() {
        return testRetries;
    }

    public void setTestRetries(Integer testRetries) {
        this.testRetries = testRetries;
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
