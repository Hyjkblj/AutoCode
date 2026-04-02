package com.autocode.agent.security;

import java.util.List;

/**
 * Normalizes paths and checks membership in workspace prefix allowlists (same rules as {@code WorkspaceAllowlistPolicy}).
 */
public final class WorkspacePrefixGuard {

    private WorkspacePrefixGuard() {
    }

    public static String normalizePath(String path) {
        if (path == null) {
            return "";
        }
        return path.replace('\\', '/').trim();
    }

    /**
     * When {@code allowedPrefixes} is empty, all paths are allowed (MVP default).
     */
    public static boolean isPathUnderAllowedPrefixes(String normalizedPath, List<String> allowedPrefixes) {
        if (allowedPrefixes == null || allowedPrefixes.isEmpty()) {
            return true;
        }
        if (normalizedPath == null || normalizedPath.isBlank()) {
            return false;
        }
        String c = normalizePath(normalizedPath);
        for (String p : allowedPrefixes) {
            if (p == null) {
                continue;
            }
            String prefix = normalizePath(p);
            if (!prefix.isEmpty() && c.startsWith(prefix)) {
                return true;
            }
        }
        return false;
    }
}
