package com.autocode.agent.runtime.intent;

import java.util.HashMap;
import java.util.Map;

public record RoutedIntent(
        String tool,
        String action,
        String skill,
        String command,
        String routeSource) {

    public static final String DEFAULT_TOOL = "command.exec";
    public static final String DEFAULT_ACTION = "run_command";
    public static final String DEFAULT_ROUTE = "fallback";

    public RoutedIntent {
        tool = firstNonBlank(tool, DEFAULT_TOOL);
        action = firstNonBlank(action, DEFAULT_ACTION);
        skill = firstNonBlank(skill, DEFAULT_TOOL);
        command = firstNonBlank(command, "git status");
        routeSource = firstNonBlank(routeSource, DEFAULT_ROUTE);
    }

    public static RoutedIntent fallback(String command) {
        return new RoutedIntent(DEFAULT_TOOL, DEFAULT_ACTION, DEFAULT_TOOL, command, DEFAULT_ROUTE);
    }

    public Map<String, Object> toToolArgs(String prompt) {
        HashMap<String, Object> args = new HashMap<>();
        args.put("command", command);
        args.put("prompt", prompt == null ? "" : prompt);
        args.put("intentSkill", skill);
        args.put("intentRoute", routeSource);
        return args;
    }

    private static String firstNonBlank(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (value == null) {
                continue;
            }
            String trimmed = value.trim();
            if (!trimmed.isEmpty()) {
                return trimmed;
            }
        }
        return null;
    }
}

