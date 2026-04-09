package com.autocode.agent.runtime.tool;

import com.autocode.protocol.model.ToolManifest;

import java.util.Map;

/**
 * A single executable capability on the agent node.
 *
 * MVP: tools are invoked by name and return structured payloads for TOOL_START/TOOL_END events.
 */
public interface Tool {
    /**
     * Self-describing manifest including name/version/arg schema/permission metadata.
     */
    ToolManifest manifest();

    default String name() {
        ToolManifest m = manifest();
        return m == null ? null : m.getName();
    }

    default String version() {
        ToolManifest m = manifest();
        return m == null ? null : m.getVersion();
    }

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

