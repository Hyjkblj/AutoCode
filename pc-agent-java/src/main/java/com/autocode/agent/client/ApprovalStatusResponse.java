/**
 * Agent-side model for approval status endpoint responses.
 */
package com.autocode.agent.client;

public class ApprovalStatusResponse {
    private String decision;

    public String getDecision() {
        return decision;
    }

    public void setDecision(String decision) {
        this.decision = decision;
    }
}
