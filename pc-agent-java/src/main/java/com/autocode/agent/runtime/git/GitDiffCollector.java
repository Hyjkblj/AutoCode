/**
 * Collects git diff statistics for FILE_PATCH_PREVIEW events (MVP implementation).
 */
package com.autocode.agent.runtime.git;

import com.autocode.agent.runtime.exec.CommandRunResult;
import com.autocode.agent.runtime.exec.CommandRunner;

import java.io.IOException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class GitDiffCollector {
    private static final int MAX_FILES = 50;

    private final CommandRunner commandRunner;

    public GitDiffCollector(CommandRunner commandRunner) {
        this.commandRunner = commandRunner;
    }

    /**
     * Returns a payload map suitable for EventType.FILE_PATCH_PREVIEW, or null when not applicable.
     */
    public Map<String, Object> collectPatchPreview(String cwd) throws IOException, InterruptedException {
        if (cwd == null || cwd.isBlank()) {
            return null;
        }

        // Fast check: if not a git repo, skip quietly.
        CommandRunResult isRepo = commandRunner.run("git rev-parse --is-inside-work-tree", Duration.ofSeconds(5), cwd);
        if (isRepo.isTimedOut() || isRepo.getExitCode() != 0) {
            return null;
        }

        CommandRunResult numstat = commandRunner.run("git diff --numstat", Duration.ofSeconds(8), cwd);
        if (numstat.isTimedOut() || numstat.getExitCode() != 0) {
            return null;
        }

        List<Map<String, Object>> files = new ArrayList<>();
        int totalAdded = 0;
        int totalRemoved = 0;

        String[] lines = (numstat.getOutput() == null ? "" : numstat.getOutput()).split("\\r?\\n");
        for (String line : lines) {
            if (line == null || line.isBlank()) {
                continue;
            }
            String[] parts = line.split("\\t", 3);
            if (parts.length < 3) {
                continue;
            }

            Integer added = parseNumstatInt(parts[0]);
            Integer removed = parseNumstatInt(parts[1]);
            String file = parts[2];

            Map<String, Object> item = new HashMap<>();
            item.put("file", file);
            item.put("added", added == null ? -1 : added);
            item.put("removed", removed == null ? -1 : removed);
            files.add(item);

            if (added != null) {
                totalAdded += added;
            }
            if (removed != null) {
                totalRemoved += removed;
            }
            if (files.size() >= MAX_FILES) {
                break;
            }
        }

        if (files.isEmpty()) {
            return null;
        }

        Map<String, Object> payload = new HashMap<>();
        payload.put("workspacePath", cwd);
        payload.put("tool", "git.diff");
        payload.put("totalAdded", totalAdded);
        payload.put("totalRemoved", totalRemoved);
        payload.put("files", files);
        payload.put("summary", "git diff (numstat)");
        return payload;
    }

    private Integer parseNumstatInt(String value) {
        if (value == null) {
            return null;
        }
        String v = value.trim();
        if (v.isEmpty() || "-".equals(v)) {
            // Binary or unknown count
            return null;
        }
        try {
            return Integer.parseInt(v);
        } catch (NumberFormatException ignored) {
            return null;
        }
    }
}

