package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;

import java.util.List;
import java.util.Locale;

/**
 * Denies command invocations that look like outbound-network operations when network is disabled.
 */
public class NetworkAccessPolicy implements ToolInvocationPolicy {
    private static final List<String> NETWORK_MARKERS = List.of(
            "curl ",
            "curl.exe",
            "wget ",
            "wget.exe",
            "invoke-webrequest",
            "iwr ",
            "irm ",
            "ssh ",
            "scp ",
            "git clone",
            "npm ",
            "pnpm ",
            "yarn ",
            "pip ",
            "pipx ",
            "http://",
            "https://"
    );

    private final boolean networkAllowed;

    public NetworkAccessPolicy(boolean networkAllowed) {
        this.networkAllowed = networkAllowed;
    }

    @Override
    public PolicyDecision evaluate(ToolCall call, ToolContext context) {
        if (networkAllowed) {
            return PolicyDecision.allow();
        }
        String command = readCommand(call);
        if (command == null) {
            return PolicyDecision.allow();
        }
        String normalized = command.trim().toLowerCase(Locale.ROOT);
        if (normalized.isEmpty()) {
            return PolicyDecision.allow();
        }
        for (String marker : NETWORK_MARKERS) {
            if (normalized.contains(marker)) {
                return PolicyDecision.deny("network_not_allowed");
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

