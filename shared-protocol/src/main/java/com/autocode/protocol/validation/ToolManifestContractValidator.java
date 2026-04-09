package com.autocode.protocol.validation;

import com.autocode.protocol.model.ToolManifest;
import com.autocode.protocol.model.ToolParamSpec;
import com.autocode.protocol.model.ToolPermissions;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Lightweight validation for {@link ToolManifest} contracts.
 */
public final class ToolManifestContractValidator {
    private ToolManifestContractValidator() {}

    public static void validate(ToolManifest manifest) {
        if (manifest == null) {
            throw new ContractViolationException("ToolManifest must not be null");
        }
        requireNonBlank(manifest.getName(), "ToolManifest.name");
        requireNonBlank(manifest.getVersion(), "ToolManifest.version");
        requireNonBlank(manifest.getAction(), "ToolManifest.action");

        validateParams(manifest.getParams());
        validatePermissions(manifest.getPermissions());
    }

    private static void validateParams(List<ToolParamSpec> params) {
        if (params == null || params.isEmpty()) {
            return;
        }
        Set<String> seen = new HashSet<>();
        for (ToolParamSpec p : params) {
            if (p == null) {
                throw new ContractViolationException("ToolManifest.params entries must not be null");
            }
            String name = requireNonBlank(p.getName(), "ToolManifest.params[].name");
            String normalized = name.trim();
            if (!seen.add(normalized)) {
                throw new ContractViolationException("ToolManifest.params contains duplicate name: " + normalized);
            }
            if (p.getEnumValues() != null) {
                for (String value : p.getEnumValues()) {
                    requireNonBlank(value, "ToolManifest.params[].enumValues[]");
                }
            }
        }
    }

    private static void validatePermissions(ToolPermissions permissions) {
        if (permissions == null) {
            return;
        }
        double riskScore = permissions.getRiskScore();
        if (Double.isNaN(riskScore) || riskScore < 0.0d || riskScore > 1.0d) {
            throw new ContractViolationException("ToolManifest.permissions.riskScore must be in [0,1]");
        }
        List<String> requiredPolicies = permissions.getRequiredPolicies();
        if (requiredPolicies != null) {
            for (String policy : requiredPolicies) {
                requireNonBlank(policy, "ToolManifest.permissions.requiredPolicies[]");
            }
        }
    }

    private static String requireNonBlank(String value, String fieldName) {
        if (value == null || value.trim().isEmpty()) {
            throw new ContractViolationException(fieldName + " is required");
        }
        return value;
    }
}
