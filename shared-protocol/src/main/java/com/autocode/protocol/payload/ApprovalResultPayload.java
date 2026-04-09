package com.autocode.protocol.payload;

import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.ApprovalContext;

/**
 * Payload for {@code EventType.APPROVAL_RESULT}.
 */
public class ApprovalResultPayload {
    private String approvalId;
    private ApprovalDecision decision;
    /**
     * Optional. End-to-end trace correlation id.
     */
    private String traceId;
    /**
     * Optional. Runtime execution correlation id.
     */
    private String runId;
    /**
     * Optional. Time spent waiting for the approval decision.
     */
    private Long waitMs;
    /**
     * Optional. Echo of the context that was approved/rejected.
     */
    private ApprovalContext context;
    /**
     * Optional. Human-readable message (e.g. rejection reason).
     */
    private String message;

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }

    public ApprovalDecision getDecision() {
        return decision;
    }

    public void setDecision(ApprovalDecision decision) {
        this.decision = decision;
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

    public Long getWaitMs() {
        return waitMs;
    }

    public void setWaitMs(Long waitMs) {
        this.waitMs = waitMs;
    }

    public ApprovalContext getContext() {
        return context;
    }

    public void setContext(ApprovalContext context) {
        this.context = context;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}

