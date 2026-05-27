package com.autocode.protocol.payload;

import java.util.List;

public class PlanApprovalRequestedPayload {
    private String planSummary;
    private List<String> steps;
    private String estimatedImpact;

    public String getPlanSummary() { return planSummary; }
    public void setPlanSummary(String planSummary) { this.planSummary = planSummary; }
    public List<String> getSteps() { return steps; }
    public void setSteps(List<String> steps) { this.steps = steps; }
    public String getEstimatedImpact() { return estimatedImpact; }
    public void setEstimatedImpact(String estimatedImpact) { this.estimatedImpact = estimatedImpact; }
}
