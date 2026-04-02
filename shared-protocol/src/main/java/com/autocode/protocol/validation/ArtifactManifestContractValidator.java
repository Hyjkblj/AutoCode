package com.autocode.protocol.validation;

import com.autocode.protocol.model.ArtifactManifest;
import com.autocode.protocol.model.ArtifactMetadata;

import java.util.List;

/**
 * Lightweight validation for {@link ArtifactManifest} (v1).
 */
public final class ArtifactManifestContractValidator {
    private ArtifactManifestContractValidator() {}

    public static void validate(ArtifactManifest manifest) {
        if (manifest == null) {
            throw new ContractViolationException("ArtifactManifest must not be null");
        }
        if (manifest.getSchemaVersion() != 1) {
            throw new ContractViolationException("Unsupported ArtifactManifest.schemaVersion: " + manifest.getSchemaVersion());
        }
        List<ArtifactMetadata> artifacts = manifest.getArtifacts();
        if (artifacts == null || artifacts.isEmpty()) {
            throw new ContractViolationException("ArtifactManifest.artifacts is required and must not be empty");
        }
        for (ArtifactMetadata a : artifacts) {
            if (a == null) {
                throw new ContractViolationException("ArtifactManifest.artifacts entries must not be null");
            }
            if (isBlank(a.getArtifactId())) {
                throw new ContractViolationException("artifact.artifactId is required");
            }
            if (isBlank(a.getType())) {
                throw new ContractViolationException("artifact.type is required");
            }
        }
        String def = manifest.getDefaultArtifactId();
        if (!isBlank(def)) {
            boolean found = false;
            for (ArtifactMetadata a : artifacts) {
                if (def.equals(a.getArtifactId())) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                throw new ContractViolationException("ArtifactManifest.defaultArtifactId must match an artifact.artifactId");
            }
        }
    }

    private static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}
