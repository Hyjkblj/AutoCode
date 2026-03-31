/**
 * Safety policy for validating and risk-rating commands derived from prompts.
 */
package com.autocode.agent.security;

import java.util.List;
import java.util.Locale;

public class CommandSafetyPolicy {
    private final List<String> allowedCommandPrefixes;

    public CommandSafetyPolicy(List<String> allowedCommandPrefixes) {
        this.allowedCommandPrefixes = allowedCommandPrefixes;
    }

    public boolean isAllowed(String command) {
        String normalized = command.trim().toLowerCase(Locale.ROOT);
        return allowedCommandPrefixes.stream().anyMatch(prefix -> normalized.startsWith(prefix.toLowerCase(Locale.ROOT)));
    }

    public boolean requiresApproval(String prompt, String command) {
        String text = (prompt + " " + command).toLowerCase(Locale.ROOT);
        return text.contains("push") || text.contains("deploy") || text.contains("rm ") || text.contains("delete") || text.contains("curl ");
    }
}
