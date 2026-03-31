/**
 * Request payload for approving or rejecting a pending approval.
 */
package com.autocode.controlplane.api;

import jakarta.validation.constraints.NotBlank;

public class ApprovalDecisionRequest {
    @NotBlank
    private String approvalId;

    @NotBlank
    private String decision;

    private String comment;

    public String getApprovalId() {
        return approvalId;
    }

    public void setApprovalId(String approvalId) {
        this.approvalId = approvalId;
    }

    public String getDecision() {
        return decision;
    }

    public void setDecision(String decision) {
        this.decision = decision;
    }

    public String getComment() {
        return comment;
    }

    public void setComment(String comment) {
        this.comment = comment;
    }
}
