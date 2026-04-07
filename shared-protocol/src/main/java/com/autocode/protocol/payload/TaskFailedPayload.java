package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TASK_FAILED}.
 */
public class TaskFailedPayload {
    /**
     * Machine-readable failure reason.
     */
    private String reason;
    /**
     * Optional human-readable detail.
     */
    private String detail;
    /**
     * Optional producer-specific error code.
     */
    private String errorCode;

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

    public String getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(String errorCode) {
        this.errorCode = errorCode;
    }
}
