package com.autocode.agent.runtime.tool;

import java.util.Map;

/**
 * Structured result of a tool execution, suitable for TOOL_END payload.
 */
public class ToolExecutionResult {
    private final Map<String, Object> toolEndPayload;
    private final boolean success;
    private final boolean retryable;

    public ToolExecutionResult(Map<String, Object> toolEndPayload, boolean success, boolean retryable) {
        this.toolEndPayload = toolEndPayload;
        this.success = success;
        this.retryable = retryable;
    }

    public Map<String, Object> getToolEndPayload() {
        return toolEndPayload;
    }

    public boolean isSuccess() {
        return success;
    }

    public boolean isRetryable() {
        return retryable;
    }
}

