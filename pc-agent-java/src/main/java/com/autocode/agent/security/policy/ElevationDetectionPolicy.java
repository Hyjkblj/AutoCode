package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;

import java.util.List;
import java.util.Locale;

/**
 * Denies commands that attempt privilege escalation on Linux/macOS/Windows shells.
 */
public class ElevationDetectionPolicy implements ToolInvocationPolicy {
    private static final List<String> ELEVATION_MARKERS = List.of(
            "sudo ",
            " su ",
            "runas ",
            "-verb runas",
            "pkexec ",
            "doas ",
            "set-executionpolicy "
    );

    @Override
    public PolicyDecision evaluate(ToolCall call, ToolContext context) {
        String command = readCommand(call);
        if (command == null) {
            return PolicyDecision.allow();
        }
        String normalized = (" " + command.trim().toLowerCase(Locale.ROOT) + " ");
        if (normalized.isBlank()) {
            return PolicyDecision.allow();
        }
        for (String marker : ELEVATION_MARKERS) {
            if (normalized.contains(marker)) {
                return PolicyDecision.deny("elevation_not_allowed");
            }
        }
        return PolicyDecision.allow();
    }

    private static String readCommand(ToolCall call) {
        if (call == null || call.getArgs() == null) {
            return null;
        }
        Object raw = call.getArgs().get("command");
        if (!(raw instanceof String s)) {
            return null;
        }
        return s;
    }
}

