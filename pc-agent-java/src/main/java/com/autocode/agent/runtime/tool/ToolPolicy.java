package com.autocode.agent.runtime.tool;

/**
 * Tool policy controls whether a tool call is allowed and whether it needs approval.
 */
public interface ToolPolicy {
    boolean isAllowed(ToolCall call);

    boolean requiresApproval(ToolCall call);
}

