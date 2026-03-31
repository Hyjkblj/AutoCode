/**
 * Request payload for creating a new task.
 */
package com.autocode.controlplane.api;

import jakarta.validation.constraints.NotBlank;

public class CreateTaskRequest {
    @NotBlank
    private String projectId;

    @NotBlank
    private String prompt;

    @NotBlank
    private String assistant;

    /**
     * 任务执行的工作区路径（可选）。若不提供，Agent 将使用自身进程的默认工作目录。
     */
    private String workspacePath;

    /**
     * 任务期望的 Agent Profile（可选）：coder/reviewer/tester。
     */
    private String agentProfile = "coder";

    /**
     * 串行 lane key（可选）。相同 sessionKey 的任务在控制平面侧尽量串行派发。
     */
    private String sessionKey;

    private String inputMode = "voice_text";
    private String riskPolicy = "strict_approval";

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
}
