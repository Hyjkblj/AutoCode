package com.autocode.protocol.validation;

import com.autocode.protocol.model.SandboxExecuteRequest;
import com.autocode.protocol.model.SandboxExecuteResponse;

/**
 * Lightweight validation for sandbox execute request/response contracts (v1).
 */
public final class SandboxExecuteContractValidator {
    private SandboxExecuteContractValidator() {}

    public static void validateRequest(SandboxExecuteRequest request) {
        if (request == null) {
            throw new ContractViolationException("SandboxExecuteRequest is required");
        }
        requireNonBlank(request.getTaskId(), "taskId");
        requireNonBlank(request.getCommand(), "command");
        Long timeout = request.getApprovalTimeoutSeconds();
        if (timeout != null && timeout <= 0) {
            throw new ContractViolationException("approvalTimeoutSeconds must be > 0 when provided");
        }
    }

    public static void validateResponse(SandboxExecuteResponse response) {
        if (response == null) {
            throw new ContractViolationException("SandboxExecuteResponse is required");
        }
        requireNonBlank(response.getStatus(), "status");
        if (response.isOk()) {
            // For success responses we expect machine-readable execution output status.
            requireNonBlank(response.getTool(), "tool");
        }
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.trim().isEmpty()) {
            throw new ContractViolationException(field + " is required");
        }
    }
}
