package com.autocode.protocol.validation;

import com.autocode.protocol.model.SandboxErrorResponse;
import com.autocode.protocol.model.SandboxHealthResponse;
import com.autocode.protocol.model.SandboxToolsResponse;
import com.autocode.protocol.model.ToolManifest;

/**
 * Lightweight validation for sandbox health/error/tools HTTP contracts (v1).
 */
public final class SandboxHttpContractValidator {
    private SandboxHttpContractValidator() {}

    public static void validateHealthResponse(SandboxHealthResponse response) {
        if (response == null) {
            throw new ContractViolationException("SandboxHealthResponse is required");
        }
        if (!response.isOk()) {
            throw new ContractViolationException("SandboxHealthResponse.ok must be true");
        }
        requireNonBlank(response.getStatus(), "status");
    }

    public static void validateErrorResponse(SandboxErrorResponse response) {
        if (response == null) {
            throw new ContractViolationException("SandboxErrorResponse is required");
        }
        if (response.isOk()) {
            throw new ContractViolationException("SandboxErrorResponse.ok must be false");
        }
        requireNonBlank(response.getStatus(), "status");
        requireNonBlank(response.getError(), "error");
    }

    public static void validateToolsResponse(SandboxToolsResponse response) {
        if (response == null) {
            throw new ContractViolationException("SandboxToolsResponse is required");
        }
        if (!response.isOk()) {
            throw new ContractViolationException("SandboxToolsResponse.ok must be true");
        }
        if (response.getTools() == null) {
            throw new ContractViolationException("tools is required");
        }
        for (ToolManifest manifest : response.getTools()) {
            ToolManifestContractValidator.validate(manifest);
        }
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.trim().isEmpty()) {
            throw new ContractViolationException(field + " is required");
        }
    }
}
