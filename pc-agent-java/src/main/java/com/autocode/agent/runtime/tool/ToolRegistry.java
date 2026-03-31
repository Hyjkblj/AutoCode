package com.autocode.agent.runtime.tool;

import java.util.HashMap;
import java.util.Map;

/**
 * Simple in-memory registry for tools.
 */
public class ToolRegistry {
    private final Map<String, Tool> tools = new HashMap<>();

    public ToolRegistry register(Tool tool) {
        if (tool == null || tool.name() == null || tool.name().isBlank()) {
            throw new IllegalArgumentException("tool name required");
        }
        tools.put(tool.name(), tool);
        return this;
    }

    public ToolRegistry clear() {
        tools.clear();
        return this;
    }

    public Tool getRequired(String name) {
        Tool tool = tools.get(name);
        if (tool == null) {
            throw new IllegalArgumentException("unknown tool: " + name);
        }
        return tool;
    }
}

