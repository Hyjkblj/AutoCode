package com.autocode.agent.runtime.tool;

import com.autocode.protocol.model.ToolManifest;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.TreeMap;

/**
 * In-memory registry for tools with version-aware lookup.
 */
public class ToolRegistry {
    private static final Comparator<String> VERSION_COMPARATOR = ToolRegistry::compareVersions;

    private final Map<String, NavigableMap<String, Tool>> tools = new HashMap<>();

    public ToolRegistry register(Tool tool) {
        if (tool == null || tool.manifest() == null) {
            throw new IllegalArgumentException("tool manifest required");
        }
        ToolManifest manifest = tool.manifest();
        String name = normalize(manifest.getName());
        String version = normalize(manifest.getVersion());
        if (name == null) {
            throw new IllegalArgumentException("tool name required");
        }
        if (version == null) {
            throw new IllegalArgumentException("tool version required");
        }
        String interfaceName = normalize(tool.name());
        if (interfaceName != null && !interfaceName.equals(name)) {
            throw new IllegalArgumentException("tool.name() must match manifest.name");
        }
        tools.computeIfAbsent(name, ignored -> new TreeMap<>(VERSION_COMPARATOR))
                .put(version, tool);
        return this;
    }

    public ToolRegistry clear() {
        tools.clear();
        return this;
    }

    public Tool getRequired(String name) {
        return getRequired(name, null);
    }

    public Tool getRequired(String name, String version) {
        String normalizedName = normalize(name);
        NavigableMap<String, Tool> versions = normalizedName == null ? null : tools.get(normalizedName);
        if (versions == null || versions.isEmpty()) {
            throw new IllegalArgumentException("unknown tool: " + name);
        }
        String normalizedVersion = normalize(version);
        if (normalizedVersion != null) {
            Tool exact = versions.get(normalizedVersion);
            if (exact == null) {
                throw new IllegalArgumentException("unknown tool version: " + name + "@" + version);
            }
            return exact;
        }
        return versions.lastEntry().getValue();
    }

    public List<ToolManifest> listManifests() {
        ArrayList<ToolManifest> manifests = new ArrayList<>();
        TreeMap<String, NavigableMap<String, Tool>> sortedByName = new TreeMap<>(tools);
        for (NavigableMap<String, Tool> byVersion : sortedByName.values()) {
            for (Tool tool : byVersion.values()) {
                manifests.add(tool.manifest());
            }
        }
        return List.copyOf(manifests);
    }

    private static String normalize(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }

    private static int compareVersions(String left, String right) {
        if (left.equals(right)) {
            return 0;
        }
        String[] l = left.split("\\.");
        String[] r = right.split("\\.");
        int max = Math.max(l.length, r.length);
        for (int i = 0; i < max; i++) {
            String lv = i < l.length ? l[i] : "0";
            String rv = i < r.length ? r[i] : "0";
            int cmp = compareVersionPart(lv, rv);
            if (cmp != 0) {
                return cmp;
            }
        }
        return left.compareTo(right);
    }

    private static int compareVersionPart(String left, String right) {
        if (left.chars().allMatch(Character::isDigit) && right.chars().allMatch(Character::isDigit)) {
            return Integer.compare(Integer.parseInt(left), Integer.parseInt(right));
        }
        return left.compareTo(right);
    }
}

