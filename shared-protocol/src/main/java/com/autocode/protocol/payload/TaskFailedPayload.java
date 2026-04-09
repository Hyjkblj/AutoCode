package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TASK_FAILED}.
 *
 * Recommended standardized reasons for nl2web MVP:
 * <ul>
 *   <li>{@link #REASON_UNSUPPORTED_TARGET}</li>
 *   <li>{@link #REASON_TEMPLATE_GENERATION_FAILED}</li>
 *   <li>{@link #REASON_ARTIFACT_PACK_FAILED}</li>
 *   <li>{@link #REASON_ARTIFACT_PUBLISH_FAILED}</li>
 *   <li>{@link #REASON_EVENT_PUBLISH_FAILED}</li>
 * </ul>
 */
public class TaskFailedPayload {
    public static final String REASON_UNSUPPORTED_TARGET = "unsupported_target";
    public static final String REASON_TEMPLATE_GENERATION_FAILED = "template_generation_failed";
    public static final String REASON_ARTIFACT_PACK_FAILED = "artifact_pack_failed";
    public static final String REASON_ARTIFACT_PUBLISH_FAILED = "artifact_publish_failed";
    public static final String REASON_EVENT_PUBLISH_FAILED = "event_publish_failed";

    /**
     * Required machine-readable reason.
     */
    private String reason;

    /**
     * Optional provider-specific error code.
     */
    private String errorCode;

    /**
     * Optional human-readable detail.
     */
    private String detail;

    /**
     * Optional trace correlation id.
     */
    private String traceId;

    /**
     * Optional runtime execution id.
     */
    private String runId;

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(String errorCode) {
        this.errorCode = errorCode;
    }

    public String getDetail() {
        return detail;
    }

    public void setDetail(String detail) {
        this.detail = detail;
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

