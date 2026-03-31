package com.autocode.protocol.model;

import java.util.Map;

/**
 * Strong-binding approval context.
 */
public class ApprovalContext {
    /**
     * Suggested values: app.generate | app.iterate | app.publish
     */
    private String action;
    /**
     * Suggested values: claudecode.run | build.run | publish.run
     */
    private String tool;
    /**
     * B stage: path; A stage: workspaceId.
     */
    private String workspaceRef;
    /**
     * Hash of normalized inputs to prevent drift.
     */
    private String inputsHash;
    /**
     * Optional opaque snapshot (template selection/spec lock/etc.).
     */
    private Map<String, Object> inputs;

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
    }

    public String getTool() {
        return tool;
    }

    public void setTool(String tool) {
        this.tool = tool;
    }

    public String getWorkspaceRef() {
        return workspaceRef;
    }

    public void setWorkspaceRef(String workspaceRef) {
        this.workspaceRef = workspaceRef;
    }

    public String getInputsHash() {
        return inputsHash;
    }

    public void setInputsHash(String inputsHash) {
        this.inputsHash = inputsHash;
    }

    public Map<String, Object> getInputs() {
        return inputs;
    }

    public void setInputs(Map<String, Object> inputs) {
        this.inputs = inputs;
    }
}

