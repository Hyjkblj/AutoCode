package com.autocode.agent.security.policy;

import com.autocode.agent.runtime.tool.ToolCall;
import com.autocode.agent.runtime.tool.ToolContext;
import com.autocode.agent.security.WorkspacePrefixGuard;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * For write-like commands, denies absolute path targets outside the allowed workspace prefixes.
 */
public class FileReadWritePolicy implements ToolInvocationPolicy {
    private static final List<String> WRITE_MARKERS = List.of(
            "rm ",
            "del ",
            "erase ",
            "rmdir ",
            "rd ",
            "remove-item ",
            "move-item ",
            "copy-item ",
            "new-item ",
            "mv ",
            "move ",
            "cp ",
            "copy ",
            "xcopy ",
            "robocopy ",
            "mkdir ",
            "md ",
            "touch ",
            "out-file ",
            "set-content ",
            "add-content ",
            " tee "
    );

    private static final List<String> DESTRUCTIVE_MARKERS = List.of(
            "rm ",
            "del ",
            "erase ",
            "rmdir ",
            "rd ",
            "remove-item "
    );

    private static final Pattern ABSOLUTE_PATH = Pattern.compile(
            "(?i)(?:(?<=^)|(?<=[\\s\"']))([a-z]:[\\\\/][^\\s\"'|;&]+|/[^\\s\"'|;&]+)"
    );
    private static final Pattern PATH_TOKEN = Pattern.compile(
            "(\"[^\"]*\"|'[^']*'|[^\\s\"'|;&]+)"
    );

    private final List<String> allowedPrefixes;

    public FileReadWritePolicy(List<String> allowedPrefixes) {
        this.allowedPrefixes = allowedPrefixes == null ? List.of() : allowedPrefixes.stream()
                .map(WorkspacePrefixGuard::normalizePath)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
    }

    @Override
    public PolicyDecision evaluate(ToolCall call, ToolContext context) {
        if (allowedPrefixes.isEmpty()) {
            return PolicyDecision.allow();
        }
        String command = readCommand(call);
        if (command == null || command.isBlank()) {
            return PolicyDecision.allow();
        }
        String normalized = " " + command.trim().toLowerCase(Locale.ROOT) + " ";
        if (!isWriteLike(normalized)) {
            return PolicyDecision.allow();
        }

        boolean destructive = isDestructive(normalized);
        for (String path : extractPathCandidates(command, context == null ? null : context.getCwd())) {
            if (destructive && isRootPath(path)) {
                return PolicyDecision.deny("root_write_blocked");
            }
            if (!WorkspacePrefixGuard.isPathUnderAllowedPrefixes(path, allowedPrefixes)) {
                return PolicyDecision.deny("write_path_not_allowed");
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

    private static boolean isWriteLike(String normalizedCommand) {
        if (normalizedCommand == null || normalizedCommand.isBlank()) {
            return false;
        }
        if (normalizedCommand.contains(" > ") || normalizedCommand.contains(" >> ")) {
            return true;
        }
        for (String marker : WRITE_MARKERS) {
            if (normalizedCommand.contains(marker)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isDestructive(String normalizedCommand) {
        if (normalizedCommand == null || normalizedCommand.isBlank()) {
            return false;
        }
        for (String marker : DESTRUCTIVE_MARKERS) {
            if (normalizedCommand.contains(marker)) {
                return true;
            }
        }
        return false;
    }

    private static List<String> extractAbsolutePathCandidates(String command) {
        LinkedHashSet<String> candidates = new LinkedHashSet<>();
        Matcher matcher = ABSOLUTE_PATH.matcher(command);
        while (matcher.find()) {
            String raw = trimQuotes(matcher.group(1));
            if (raw == null || raw.isBlank()) {
                continue;
            }
            // Skip URL fragments: http://host/path
            int idx = raw.indexOf("://");
            if (idx > 0) {
                continue;
            }
            candidates.add(raw);
        }
        return new ArrayList<>(candidates);
    }

    private static List<String> extractPathCandidates(String command, String cwd) {
        LinkedHashSet<String> candidates = new LinkedHashSet<>();
        for (String abs : extractAbsolutePathCandidates(command)) {
            String normalized = WorkspacePrefixGuard.normalizePath(abs);
            if (!normalized.isBlank()) {
                candidates.add(normalized);
            }
        }
        String normalizedCwd = WorkspacePrefixGuard.normalizePath(cwd);
        if (!normalizedCwd.isBlank()) {
            Matcher matcher = PATH_TOKEN.matcher(command);
            while (matcher.find()) {
                String token = trimQuotes(matcher.group(1));
                String resolved = resolveRelativePathCandidate(token, normalizedCwd);
                if (resolved == null || resolved.isBlank()) {
                    continue;
                }
                candidates.add(resolved);
            }
        }
        return new ArrayList<>(candidates);
    }

    private static String resolveRelativePathCandidate(String token, String normalizedCwd) {
        if (token == null || token.isBlank()) {
            return null;
        }
        String trimmed = token.trim();
        String lowered = trimmed.toLowerCase(Locale.ROOT);
        if (trimmed.startsWith("-")) {
            return null;
        }
        if (trimmed.startsWith("$") || trimmed.startsWith("%")) {
            return null;
        }
        if (lowered.contains("://")) {
            return null;
        }
        if (ABSOLUTE_PATH.matcher(trimmed).matches()) {
            return null;
        }
        boolean pathLike = lowered.startsWith("./")
                || lowered.startsWith(".\\")
                || lowered.startsWith("../")
                || lowered.startsWith("..\\")
                || lowered.startsWith("~/")
                || lowered.startsWith("~\\")
                || trimmed.contains("/")
                || trimmed.contains("\\");
        if (!pathLike) {
            return null;
        }

        if (lowered.startsWith("~/") || lowered.startsWith("~\\")) {
            return WorkspacePrefixGuard.normalizePath(trimmed);
        }
        return WorkspacePrefixGuard.normalizePath(normalizedCwd + "/" + trimmed);
    }

    private static boolean isRootPath(String normalizedPath) {
        if (normalizedPath == null) {
            return false;
        }
        String p = normalizedPath.trim().toLowerCase(Locale.ROOT);
        if ("/".equals(p)) {
            return true;
        }
        return p.matches("^[a-z]:/?$");
    }

    private static String trimQuotes(String raw) {
        if (raw == null) {
            return null;
        }
        String trimmed = raw.trim();
        if (trimmed.length() < 2) {
            return trimmed;
        }
        char first = trimmed.charAt(0);
        char last = trimmed.charAt(trimmed.length() - 1);
        if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
            return trimmed.substring(1, trimmed.length() - 1).trim();
        }
        return trimmed;
    }
}

