package com.autocode.protocol.payload;

import com.autocode.protocol.model.ArtifactMetadata;

/**
 * Payload for {@code EventType.DEPLOY_RESULT}.
 */
public class DeployResultPayload {
    /**
     * Required. Correlates with {@code DEPLOY_PLAN.payload.requestId}.
     */
    private String requestId;

    /**
     * Optional. Provider deployment id.
     */
    private String deploymentId;

    /**
     * Optional. Target environment (for example: staging, production).
     */
    private String environment;

    /**
     * Required. Suggested values: accepted | running | success | failed | rejected | canceled.
     */
    private String status;

    /**
     * Optional. Human-readable status details.
     */
    private String message;

    /**
     * Optional. Entrypoint URL after deployment is complete.
     */
    private String endpointUrl;

    /**
     * Optional ISO-8601 start time.
     */
    private String startedAt;

    /**
     * Optional ISO-8601 finish time.
     */
    private String finishedAt;

    /**
     * Optional artifact with deployment report/log details.
     */
    private ArtifactMetadata resultArtifact;

    public String getRequestId() {
        return requestId;
    }

    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }

    public String getDeploymentId() {
        return deploymentId;
    }

    public void setDeploymentId(String deploymentId) {
        this.deploymentId = deploymentId;
    }

    public String getEnvironment() {
        return environment;
    }

    public void setEnvironment(String environment) {
        this.environment = environment;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getEndpointUrl() {
        return endpointUrl;
    }

    public void setEndpointUrl(String endpointUrl) {
        this.endpointUrl = endpointUrl;
    }

    public String getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(String startedAt) {
        this.startedAt = startedAt;
    }

    public String getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(String finishedAt) {
        this.finishedAt = finishedAt;
    }

    public ArtifactMetadata getResultArtifact() {
        return resultArtifact;
    }

    public void setResultArtifact(ArtifactMetadata resultArtifact) {
        this.resultArtifact = resultArtifact;
    }
}
