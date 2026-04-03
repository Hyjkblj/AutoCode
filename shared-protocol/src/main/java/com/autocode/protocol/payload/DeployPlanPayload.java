package com.autocode.protocol.payload;

import com.autocode.protocol.model.ApprovalContext;
import com.autocode.protocol.model.ArtifactMetadata;

import java.util.Map;

/**
 * Payload for {@code EventType.DEPLOY_PLAN}.
 */
public class DeployPlanPayload {
    /**
     * Required. Stable request correlation id.
     */
    private String requestId;

    /**
     * Required. Target deployment environment (for example: staging, production).
     */
    private String environment;

    /**
     * Optional. Suggested values: rolling | blue-green | canary.
     */
    private String strategy;

    /**
     * Optional. Principal that triggered deployment (user/service account).
     */
    private String triggeredBy;

    /**
     * Required. Artifact selected for deployment.
     */
    private ArtifactMetadata artifact;

    /**
     * Optional. Strong-binding approval context when publish is gated.
     */
    private ApprovalContext context;

    /**
     * Optional. Provider-specific options.
     */
    private Map<String, Object> options;

    public String getRequestId() {
        return requestId;
    }

    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }

    public String getEnvironment() {
        return environment;
    }

    public void setEnvironment(String environment) {
        this.environment = environment;
    }

    public String getStrategy() {
        return strategy;
    }

    public void setStrategy(String strategy) {
        this.strategy = strategy;
    }

    public String getTriggeredBy() {
        return triggeredBy;
    }

    public void setTriggeredBy(String triggeredBy) {
        this.triggeredBy = triggeredBy;
    }

    public ArtifactMetadata getArtifact() {
        return artifact;
    }

    public void setArtifact(ArtifactMetadata artifact) {
        this.artifact = artifact;
    }

    public ApprovalContext getContext() {
        return context;
    }

    public void setContext(ApprovalContext context) {
        this.context = context;
    }

    public Map<String, Object> getOptions() {
        return options;
    }

    public void setOptions(Map<String, Object> options) {
        this.options = options;
    }
}
