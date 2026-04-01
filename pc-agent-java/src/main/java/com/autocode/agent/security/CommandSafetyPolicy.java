/**
 * Safety policy for validating and risk-rating commands derived from prompts.
 */
package com.autocode.agent.security;

import java.util.List;
import java.util.Locale;

/**
 * Default-deny prefix allowlist plus optional outbound-network gate, aligned with claudecode-runner
 * {@code ExecutionPolicy} markers.
 */
public class CommandSafetyPolicy {
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
            "npm ",
            "pnpm ",
            "yarn ",
            "pip ",
            "pipx ",
            "git clone",
            "apt-get",
            "choco ",
            "winget "
    );

    private final List<String> allowedCommandPrefixes;
    private final boolean networkAllowed;

    /**
     * Backward-compatible: network checks disabled (prefix allowlist only).
     */
    public CommandSafetyPolicy(List<String> allowedCommandPrefixes) {
        this(allowedCommandPrefixes, true);
    }

    public CommandSafetyPolicy(List<String> allowedCommandPrefixes, boolean networkAllowed) {
        this.allowedCommandPrefixes = allowedCommandPrefixes;
        this.networkAllowed = networkAllowed;
    }

    public boolean isAllowed(String command) {
        String normalized = command.trim().toLowerCase(Locale.ROOT);
        if (allowedCommandPrefixes.isEmpty()) {
            return false;
        }
        boolean prefixOk = allowedCommandPrefixes.stream()
                .anyMatch(prefix -> normalized.startsWith(prefix.toLowerCase(Locale.ROOT)));
        if (!prefixOk) {
            return false;
        }
        if (!networkAllowed && looksLikeNetwork(normalized)) {
            return false;
        }
        return true;
    }

    public boolean requiresApproval(String prompt, String command) {
        String text = (prompt + " " + command).toLowerCase(Locale.ROOT);
        return text.contains("push")
                || text.contains("deploy")
                || text.contains("rm ")
                || text.contains("delete")
                || text.contains("curl ")
                || text.contains("invoke-webrequest")
                || text.contains("format ")
                || text.contains("del ")
                || text.contains("rmdir");
    }

    private static boolean looksLikeNetwork(String normalizedCommandLine) {
        for (String m : NETWORK_MARKERS) {
            if (normalizedCommandLine.contains(m)) {
                return true;
            }
        }
        return false;
    }
}
