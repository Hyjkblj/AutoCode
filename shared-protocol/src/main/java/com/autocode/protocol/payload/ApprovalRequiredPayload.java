package com.autocode.protocol.payload;

import com.autocode.protocol.model.ApprovalContext;

/**
 * Payload for {@code EventType.APPROVAL_REQUIRED}.
 */
public class ApprovalRequiredPayload {
    /**
     * Required. Correlation id for later {@code APPROVAL_RESULT}.
     */
    private String approvalId;
    /**
     * Required. Strong-binding context.
     */
    private ApprovalContext context;
    /**
     * Optional. Human-readable reason.
     */
    private String reason;

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }

    public ApprovalContext getContext() {
        return context;
    }

    public void setContext(ApprovalContext context) {
        this.context = context;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }
}

