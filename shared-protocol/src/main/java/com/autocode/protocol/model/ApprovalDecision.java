/**
 * Approval decision for high-risk actions.
 */
package com.autocode.protocol.model;

import com.fasterxml.jackson.annotation.JsonCreator;

import java.util.Locale;

public enum ApprovalDecision {
    PENDING,
    APPROVE,
    REJECT;

    /**
     * Accept both upper/lower/mixed-case inputs for cross-language payload compatibility.
     */
    @JsonCreator
    public static ApprovalDecision fromValue(String value) {
        if (value == null || value.isBlank()) {
            return PENDING;
        }
        return switch (value.trim().toLowerCase(Locale.ROOT)) {
            case "approve", "approved" -> APPROVE;
            case "reject", "rejected" -> REJECT;
            default -> PENDING;
        };
    }
}
