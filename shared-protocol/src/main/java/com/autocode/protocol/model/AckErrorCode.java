/**
 * Shared error codes for the event ACK protocol.
 * Both Java (control-plane) and Python (python-agent) sides must use these codes
 * to ensure consistent error classification and retry semantics.
 */
package com.autocode.protocol.model;

public enum AckErrorCode {
    /** Node ID is empty or malformed. Non-retryable. */
    INVALID_NODE_ID(false),

    /** Node has not registered with the control plane. Non-retryable. */
    NODE_NOT_REGISTERED(false),

    /** Event ID is missing or blank. Non-retryable. */
    MISSING_EVENT_ID(false),

    /** Target task does not exist. Non-retryable. */
    TASK_NOT_FOUND(false),

    /** Node is not authorized to ingest events for this task. Non-retryable. */
    ACCESS_DENIED(false),

    /** Event failed protocol validation (missing fields, invalid payload). Non-retryable. */
    INVALID_EVENT(false),

    /** Event attempts an illegal task state transition. Non-retryable. */
    ILLEGAL_STATE_TRANSITION(false),

    /** Internal processing error (transient). Retryable. */
    PROCESSING_ERROR(true);

    private final boolean retryable;

    AckErrorCode(boolean retryable) {
        this.retryable = retryable;
    }

    /**
     * @return true if the error is transient and the agent may retry delivery.
     */
    public boolean isRetryable() {
        return retryable;
    }
}
