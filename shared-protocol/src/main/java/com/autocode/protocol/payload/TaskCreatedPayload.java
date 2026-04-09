package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TASK_CREATED}.
 */
public class TaskCreatedPayload {
    /**
     * Required. Owning project id.
     */
    private String projectId;

    /**
     * Optional. Requested assistant name/profile.
     */
    private String assistant;

    /**
     * Optional. Risk policy requested on create.
     */
    private String riskPolicy;

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public String getAssistant() {
        return assistant;
    }

    public void setAssistant(String assistant) {
        this.assistant = assistant;
    }

    public String getRiskPolicy() {
        return riskPolicy;
    }

    public void setRiskPolicy(String riskPolicy) {
        this.riskPolicy = riskPolicy;
    }
}
