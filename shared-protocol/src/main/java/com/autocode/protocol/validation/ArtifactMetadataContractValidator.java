package com.autocode.protocol.validation;

import com.autocode.protocol.model.ArtifactMetadata;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Validates optional nested structures on {@link ArtifactMetadata} (and payload maps) for v1.
 * When {@code build} is present, {@code command} must be non-blank (matches JSON Schema intent).
 */
public final class ArtifactMetadataContractValidator {
    private ArtifactMetadataContractValidator() {}

    public static void validateNestedDescriptors(ArtifactMetadata artifact) {
        if (artifact == null) {
            return;
        }
        ArtifactMetadata.BuildDescriptor build = artifact.getBuild();
        if (build != null) {
            if (isBlank(build.getCommand())) {
                throw new ContractViolationException("artifact.build.command is required when build is present");
            }
        }
    }

    /**
     * Same rules as {@link #validateNestedDescriptors(ArtifactMetadata)} for dynamic {@code artifact} objects
     * inside {@link com.autocode.protocol.model.TaskEvent#getPayload()}.
     */
    @SuppressWarnings("unchecked")
    public static void validateNestedDescriptorsFromMap(Map<String, Object> artifact) {
        if (artifact == null) {
            return;
        }
        Object build = artifact.get("build");
        if (build == null) {
            return;
        }
        if (!(build instanceof Map)) {
            throw new ContractViolationException("artifact.build must be an object");
        }
        Map<String, Object> bm = (Map<String, Object>) build;
        Object cmd = bm.get("command");
        if (!(cmd instanceof String) || isBlank((String) cmd)) {
            throw new ContractViolationException("artifact.build.command is required when build is present");
        }
    }

    /** Ensures {@code artifactId} values are unique within a manifest list (order-preserving first wins). */
    public static void assertUniqueArtifactIds(List<ArtifactMetadata> artifacts) {
        if (artifacts == null) {
            return;
        }
        Set<String> seen = new HashSet<>();
        for (ArtifactMetadata a : artifacts) {
            if (a == null) {
                continue;
            }
            String id = a.getArtifactId();
            if (isBlank(id)) {
                continue;
            }
            if (!seen.add(id.trim())) {
                throw new ContractViolationException("Duplicate artifact.artifactId in manifest: " + id.trim());
            }
        }
    }

    private static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}
