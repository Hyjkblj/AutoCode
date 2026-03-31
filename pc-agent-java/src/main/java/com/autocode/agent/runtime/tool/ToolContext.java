package com.autocode.agent.runtime.tool;

import com.autocode.protocol.model.TaskSummary;

/**
 * Invocation context for a tool call.
 */
public class ToolContext {
    private final TaskSummary task;
    private final String cwd;
    private final String approvalId;
    private final long approvalTimeoutSeconds;

    public ToolContext(TaskSummary task, String cwd, String approvalId, long approvalTimeoutSeconds) {
        this.task = task;
        this.cwd = cwd;
        this.approvalId = approvalId;
        this.approvalTimeoutSeconds = approvalTimeoutSeconds;
    }

    public TaskSummary getTask() {
        return task;
    }

    public String getCwd() {
        return cwd;
    }

    public String getApprovalId() {
        return approvalId;
    }

    public long getApprovalTimeoutSeconds() {
        return approvalTimeoutSeconds;
    }
}

