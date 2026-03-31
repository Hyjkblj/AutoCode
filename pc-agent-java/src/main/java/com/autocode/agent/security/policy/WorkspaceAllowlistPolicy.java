package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;

import java.util.List;

/**
 * Allows tool invocation only when cwd is within one of the allowed prefixes.
 *
 * Empty allowlist means "allow all" (MVP default to avoid breaking local usage).
 */
public class WorkspaceAllowlistPolicy implements ToolInvocationPolicy {
    private final List<String> allowedPrefixes;

    public WorkspaceAllowlistPolicy(List<String> allowedPrefixes) {
        this.allowedPrefixes = allowedPrefixes == null ? List.of() : allowedPrefixes.stream()
                .map(s -> s == null ? "" : s.trim())
                .filter(s -> !s.isEmpty())
                .toList();
    }

    @Override
    public PolicyDecision evaluate(ToolCall call, ToolContext context) {
        if (allowedPrefixes.isEmpty()) {
            return PolicyDecision.allow();
        }
        String cwd = context == null ? null : context.getCwd();
        if (cwd == null || cwd.isBlank()) {
            return PolicyDecision.deny("cwd_missing");
        }
        String c = normalize(cwd);
        for (String p : allowedPrefixes) {
            if (c.startsWith(normalize(p))) {
                return PolicyDecision.allow();
            }
        }
        return PolicyDecision.deny("cwd_not_allowed");
    }

    private String normalize(String path) {
        return path.replace('\\', '/').trim();
    }
}

