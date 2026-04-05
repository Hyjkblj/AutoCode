package com.autocode.protocol.model;

import java.util.ArrayList;
import java.util.List;

/**
 * Declarative permission envelope for a tool.
 */
public class ToolPermissions {
    private boolean commandExec;
    private boolean fileRead;
    private boolean fileWrite;
    private boolean networkAccess;
    private boolean approvalRequired;
    /**
     * Risk score in [0, 1], where higher means higher approval risk.
     */
    private double riskScore;
    /**
     * Policy ids this tool requires from the runtime policy chain.
     */
    private List<String> requiredPolicies = new ArrayList<>();

    public boolean isCommandExec() {
        return commandExec;
    }

    public void setCommandExec(boolean commandExec) {
        this.commandExec = commandExec;
    }

    public boolean isFileRead() {
        return fileRead;
    }

    public void setFileRead(boolean fileRead) {
        this.fileRead = fileRead;
    }

    public boolean isFileWrite() {
        return fileWrite;
    }

    public void setFileWrite(boolean fileWrite) {
        this.fileWrite = fileWrite;
    }

    public boolean isNetworkAccess() {
        return networkAccess;
    }

    public void setNetworkAccess(boolean networkAccess) {
        this.networkAccess = networkAccess;
    }

    public boolean isApprovalRequired() {
        return approvalRequired;
    }

    public void setApprovalRequired(boolean approvalRequired) {
        this.approvalRequired = approvalRequired;
    }

    public double getRiskScore() {
        return riskScore;
    }

    public void setRiskScore(double riskScore) {
        this.riskScore = riskScore;
    }

    public List<String> getRequiredPolicies() {
        return requiredPolicies;
    }

    public void setRequiredPolicies(List<String> requiredPolicies) {
        this.requiredPolicies = requiredPolicies;
    }
}
