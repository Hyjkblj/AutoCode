package com.autocode.agent.runtime.tool;

import com.autocode.protocol.model.ToolManifest;
import com.autocode.protocol.validation.ContractViolationException;
import com.autocode.protocol.validation.ToolManifestContractValidator;

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
        try {
            ToolManifestContractValidator.validate(manifest);
        } catch (ContractViolationException ex) {
            throw new IllegalArgumentException("invalid tool manifest: " + ex.getMessage(), ex);
        }
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
        ParsedVersion l = ParsedVersion.parse(left);
        ParsedVersion r = ParsedVersion.parse(right);

        int cmp = compareCoreIdentifiers(l.core(), r.core());
        if (cmp != 0) {
            return cmp;
        }
        cmp = comparePreReleaseIdentifiers(l.preRelease(), r.preRelease());
        if (cmp != 0) {
            return cmp;
        }
        return left.compareTo(right);
    }

    private static int compareCoreIdentifiers(List<String> left, List<String> right) {
        int max = Math.max(left.size(), right.size());
        for (int i = 0; i < max; i++) {
            String lv = i < left.size() ? left.get(i) : "0";
            String rv = i < right.size() ? right.get(i) : "0";
            int cmp = compareVersionPart(lv, rv);
            if (cmp != 0) {
                return cmp;
            }
        }
        return 0;
    }

    private static int comparePreReleaseIdentifiers(List<String> left, List<String> right) {
        if (left.isEmpty() && right.isEmpty()) {
            return 0;
        }
        if (left.isEmpty()) {
            return 1;
        }
        if (right.isEmpty()) {
            return -1;
        }
        int max = Math.max(left.size(), right.size());
        for (int i = 0; i < max; i++) {
            if (i >= left.size()) {
                return -1;
            }
            if (i >= right.size()) {
                return 1;
            }
            String lv = left.get(i);
            String rv = right.get(i);
            boolean leftNumeric = isNumeric(lv);
            boolean rightNumeric = isNumeric(rv);
            if (leftNumeric && rightNumeric) {
                int cmp = compareNumericStrings(lv, rv);
                if (cmp != 0) {
                    return cmp;
                }
                continue;
            }
            if (leftNumeric != rightNumeric) {
                return leftNumeric ? -1 : 1;
            }
            int cmp = lv.compareTo(rv);
            if (cmp != 0) {
                return cmp;
            }
        }
        return 0;
    }

    private static int compareVersionPart(String left, String right) {
        if (isNumeric(left) && isNumeric(right)) {
            return compareNumericStrings(left, right);
        }
        return left.compareTo(right);
    }

    private static boolean isNumeric(String value) {
        return value != null && !value.isEmpty() && value.chars().allMatch(Character::isDigit);
    }

    private static int compareNumericStrings(String left, String right) {
        String normalizedLeft = stripLeadingZeros(left);
        String normalizedRight = stripLeadingZeros(right);
        if (normalizedLeft.length() != normalizedRight.length()) {
            return Integer.compare(normalizedLeft.length(), normalizedRight.length());
        }
        return normalizedLeft.compareTo(normalizedRight);
    }

    private static String stripLeadingZeros(String value) {
        if (value == null || value.isEmpty()) {
            return "0";
        }
        int index = 0;
        while (index < value.length() - 1 && value.charAt(index) == '0') {
            index++;
        }
        return value.substring(index);
    }

    private record ParsedVersion(List<String> core, List<String> preRelease) {
        private static ParsedVersion parse(String version) {
            String raw = version == null ? "" : version.trim();
            int buildIndex = raw.indexOf('+');
            String withoutBuild = buildIndex >= 0 ? raw.substring(0, buildIndex) : raw;

            int preReleaseIndex = withoutBuild.indexOf('-');
            String core = preReleaseIndex >= 0 ? withoutBuild.substring(0, preReleaseIndex) : withoutBuild;
            String preRelease = preReleaseIndex >= 0 ? withoutBuild.substring(preReleaseIndex + 1) : "";
            return new ParsedVersion(splitIdentifiers(core), splitIdentifiers(preRelease));
        }

        private static List<String> splitIdentifiers(String value) {
            if (value == null || value.isEmpty()) {
                return List.of();
            }
            String[] parts = value.split("\\.");
            ArrayList<String> result = new ArrayList<>(parts.length);
            for (String part : parts) {
                result.add(part == null ? "" : part);
            }
            return List.copyOf(result);
        }
    }
}

