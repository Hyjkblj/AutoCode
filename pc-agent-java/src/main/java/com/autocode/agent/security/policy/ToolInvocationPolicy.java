package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;

/**
 * Evaluates whether a tool invocation is allowed.
 */
public interface ToolInvocationPolicy {
    PolicyDecision evaluate(ToolCall call, ToolContext context);
}

