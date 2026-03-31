package com.autocode.protocol.model;

import java.util.Map;

/**
 * Stable, contract-first request payload for creating a new task.
 *
 * Compatibility policy:
 * - Keep legacy flat fields (projectId/prompt/assistant/...) for existing clients.
 * - New structured sections (identity/intent/execution/risk) are optional and can be adopted incrementally.
 * - When both legacy and structured fields are present, servers MAY prefer structured fields.
 */
public class CreateTaskRequest {
    // Legacy flat fields (backward compatible)
    private String projectId;
    private String prompt;
    private String assistant;
    private String workspacePath;
    private String agentProfile;
    private String sessionKey;
    private String inputMode;
    private String riskPolicy;

    // New structured fields (all optional)
    private Identity identity;
    private Intent intent;
    private Execution execution;
    private Risk risk;

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getAssistant() {
        return assistant;
    }

    public void setAssistant(String assistant) {
        this.assistant = assistant;
    }

    public String getWorkspacePath() {
        return workspacePath;
    }

    public void setWorkspacePath(String workspacePath) {
        this.workspacePath = workspacePath;
    }

    public String getAgentProfile() {
        return agentProfile;
    }

    public void setAgentProfile(String agentProfile) {
        this.agentProfile = agentProfile;
    }

    public String getSessionKey() {
        return sessionKey;
    }

    public void setSessionKey(String sessionKey) {
        this.sessionKey = sessionKey;
    }

    public String getInputMode() {
        return inputMode;
    }

    public void setInputMode(String inputMode) {
        this.inputMode = inputMode;
    }

    public String getRiskPolicy() {
        return riskPolicy;
    }

    public void setRiskPolicy(String riskPolicy) {
        this.riskPolicy = riskPolicy;
    }

    public Identity getIdentity() {
        return identity;
    }

    public void setIdentity(Identity identity) {
        this.identity = identity;
    }

    public Intent getIntent() {
        return intent;
    }

    public void setIntent(Intent intent) {
        this.intent = intent;
    }

    public Execution getExecution() {
        return execution;
    }

    public void setExecution(Execution execution) {
        this.execution = execution;
    }

    public Risk getRisk() {
        return risk;
    }

    public void setRisk(Risk risk) {
        this.risk = risk;
    }

    public static class Identity {
        private String projectId;
        private String tenantId;
        private String idempotencyKey;
        private Map<String, String> tags;

        public String getProjectId() {
            return projectId;
        }

        public void setProjectId(String projectId) {
            this.projectId = projectId;
        }

        public String getTenantId() {
            return tenantId;
        }

        public void setTenantId(String tenantId) {
            this.tenantId = tenantId;
        }

        public String getIdempotencyKey() {
            return idempotencyKey;
        }

        public void setIdempotencyKey(String idempotencyKey) {
            this.idempotencyKey = idempotencyKey;
        }

        public Map<String, String> getTags() {
            return tags;
        }

        public void setTags(Map<String, String> tags) {
            this.tags = tags;
        }
    }

    public static class Intent {
        private String prompt;
        /**
         * Suggested values: web | miniapp
         */
        private String target;
        private String templateId;
        /**
         * Suggested values: zip | git
         */
        private String exportMode;
        private Map<String, Object> options;

        public String getPrompt() {
            return prompt;
        }

        public void setPrompt(String prompt) {
            this.prompt = prompt;
        }

        public String getTarget() {
            return target;
        }

        public void setTarget(String target) {
            this.target = target;
        }

        public String getTemplateId() {
            return templateId;
        }

        public void setTemplateId(String templateId) {
            this.templateId = templateId;
        }

        public String getExportMode() {
            return exportMode;
        }

        public void setExportMode(String exportMode) {
            this.exportMode = exportMode;
        }

        public Map<String, Object> getOptions() {
            return options;
        }

        public void setOptions(Map<String, Object> options) {
            this.options = options;
        }
    }

    public static class Execution {
        /**
         * B 阶段可直接用 path；A 阶段建议使用 workspaceId（workspaceRef）。
         */
        private String workspaceRef;
        private String workspacePath;
        private String agentProfile;
        private String sessionKey;

        public String getWorkspaceRef() {
            return workspaceRef;
        }

        public void setWorkspaceRef(String workspaceRef) {
            this.workspaceRef = workspaceRef;
        }

        public String getWorkspacePath() {
            return workspacePath;
        }

        public void setWorkspacePath(String workspacePath) {
            this.workspacePath = workspacePath;
        }

        public String getAgentProfile() {
            return agentProfile;
        }

        public void setAgentProfile(String agentProfile) {
            this.agentProfile = agentProfile;
        }

        public String getSessionKey() {
            return sessionKey;
        }

        public void setSessionKey(String sessionKey) {
            this.sessionKey = sessionKey;
        }
    }

    public static class Risk {
        /**
         * Suggested values: low | medium | high
         */
        private String riskPolicy;

        public String getRiskPolicy() {
            return riskPolicy;
        }

        public void setRiskPolicy(String riskPolicy) {
            this.riskPolicy = riskPolicy;
        }
    }
}
