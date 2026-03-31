package com.autocode.agent.runtime.tool;

import java.util.Map;

/**
 * A single executable capability on the agent node.
 *
 * MVP: tools are invoked by name and return structured payloads for TOOL_START/TOOL_END events.
 */
public interface Tool {
    String name();

    ToolPolicy policy();

    /**
     * Build payload for APPROVAL_REQUIRED event when approval is needed.
     */
    Map<String, Object> buildApprovalPayload(ToolCall call, ToolContext context);

    /**
     * Execute the tool call and return TOOL_END payload fields.
     */
    ToolExecutionResult execute(ToolCall call, ToolContext context) throws Exception;
}

