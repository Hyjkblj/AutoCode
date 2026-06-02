package com.autocode.approval.dto;

import com.autocode.protocol.model.ApprovalDecision;
import jakarta.validation.constraints.NotNull;

/**
 * DTO for submitting an approval decision.
 */
public class ApprovalDecisionDto {

    @NotNull(message = "Decision is required")
    private ApprovalDecision decision;

    private String message;
    private String decidedBy;

    // Getters and Setters

    public ApprovalDecision getDecision() {
        return decision;
    }

    public void setDecision(ApprovalDecision decision) {
        this.decision = decision;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getDecidedBy() {
        return decidedBy;
    }

    public void setDecidedBy(String decidedBy) {
        this.decidedBy = decidedBy;
    }
}
