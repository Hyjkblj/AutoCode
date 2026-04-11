package com.autocode.agent.security;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;
import java.util.Locale;

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
        String raw = path.replace('\\', '/').trim();
        if (raw.isEmpty()) {
            return "";
        }

        String prefix = "";
        String rest = raw;
        if (raw.length() >= 2 && Character.isLetter(raw.charAt(0)) && raw.charAt(1) == ':') {
            prefix = raw.substring(0, 2).toLowerCase(Locale.ROOT);
            rest = raw.substring(2);
        }
        boolean absolute = rest.startsWith("/");
        if (absolute) {
            rest = rest.substring(1);
        }

        Deque<String> stack = new ArrayDeque<>();
        for (String segment : rest.split("/+")) {
            String s = segment == null ? "" : segment.trim();
            if (s.isEmpty() || ".".equals(s)) {
                continue;
            }
            if ("..".equals(s)) {
                if (!stack.isEmpty() && !"..".equals(stack.peekLast())) {
                    stack.removeLast();
                    continue;
                }
                if (!absolute && prefix.isEmpty()) {
                    stack.addLast(s);
                }
                continue;
            }
            stack.addLast(s);
        }

        StringBuilder sb = new StringBuilder();
        if (!prefix.isEmpty()) {
            sb.append(prefix).append('/');
        } else if (absolute) {
            sb.append('/');
        }
        boolean first = true;
        for (String s : stack) {
            if (!first) {
                sb.append('/');
            }
            sb.append(s);
            first = false;
        }
        String normalized = trimTrailingSlash(sb.toString());
        if (normalized.isEmpty() && !prefix.isEmpty()) {
            return prefix + "/";
        }
        if (normalized.isEmpty() && absolute) {
            return "/";
        }
        return normalized;
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
        String c = normalizeForCompare(normalizePath(normalizedPath));
        for (String p : allowedPrefixes) {
            if (p == null) {
                continue;
            }
            String prefix = normalizeForCompare(normalizePath(p));
            if (prefix.isEmpty()) {
                continue;
            }
            if (c.equals(prefix)) {
                return true;
            }
            if ("/".equals(prefix)) {
                if (c.startsWith("/")) {
                    return true;
                }
                continue;
            }
            if (isDriveRoot(prefix)) {
                if (c.startsWith(prefix)) {
                    return true;
                }
                continue;
            }
            if (c.startsWith(prefix + "/")) {
                return true;
            }
        }
        return false;
    }

    /**
     * Windows file systems are case-insensitive. For drive-letter paths we compare in lowercase to
     * avoid false "cwd_not_allowed" denials caused by casing differences (e.g. Develop vs develop).
     */
    private static String normalizeForCompare(String path) {
        if (path == null) {
            return "";
        }
        // drive-letter paths: length >= 2, letter + ':', already lowercased by normalizePath
        if (path.length() >= 2 && Character.isLetter(path.charAt(0)) && path.charAt(1) == ':') {
            return path.toLowerCase(Locale.ROOT);
        }
        return path;
    }

    private static boolean isDriveRoot(String path) {
        if (path == null) {
            return false;
        }
        return path.matches("^[a-z]:/$");
    }

    private static String trimTrailingSlash(String path) {
        if (path == null || path.isEmpty()) {
            return "";
        }
        String p = path;
        while (p.length() > 1 && p.endsWith("/")) {
            if ("/".equals(p) || isDriveRoot(p)) {
                break;
            }
            p = p.substring(0, p.length() - 1);
        }
        return p;
    }
}
