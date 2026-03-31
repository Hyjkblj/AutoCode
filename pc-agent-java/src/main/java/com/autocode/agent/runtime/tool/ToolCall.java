package com.autocode.agent.runtime.tool;

import java.util.Map;

/**
 * A request to invoke a tool.
 */
public class ToolCall {
    private final String tool;
    private final String action;
    private final Map<String, Object> args;

    public ToolCall(String tool, String action, Map<String, Object> args) {
        this.tool = tool;
        this.action = action;
        this.args = args;
    }

    public String getTool() {
        return tool;
    }

    public String getAction() {
        return action;
    }

    public Map<String, Object> getArgs() {
        return args;
    }
}

