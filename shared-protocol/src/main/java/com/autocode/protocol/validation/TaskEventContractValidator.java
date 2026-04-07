package com.autocode.protocol.validation;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;

import java.util.Map;

/**
 * Lightweight contract validator for {@link TaskEvent}.
 *
 * Note: Payload is represented as a {@code Map<String, Object>} for cross-language compatibility. This validator
 * enforces required fields for a subset of events used by the platform.
 */
public final class TaskEventContractValidator {
    private TaskEventContractValidator() {}

    public static void validate(TaskEvent event) {
        if (event == null) {
            throw new ContractViolationException("TaskEvent must not be null");
        }
        if (isBlank(event.getEventId())) {
            throw new ContractViolationException("TaskEvent.eventId is required");
        }
        if (isBlank(event.getTaskId())) {
            throw new ContractViolationException("TaskEvent.taskId is required");
        }
        if (event.getType() == null) {
            throw new ContractViolationException("TaskEvent.type is required");
        }
        if (event.getTimestamp() == null) {
            throw new ContractViolationException("TaskEvent.timestamp is required");
        }
        if (event.getSeq() < 0) {
            throw new ContractViolationException("TaskEvent.seq must be >= 0");
        }
        if (event.getEventVersion() != 1) {
            throw new ContractViolationException("Unsupported TaskEvent.eventVersion: " + event.getEventVersion());
        }

        Map<String, Object> payload = event.getPayload();
        // payload map itself is optional for legacy events, but event-specific requirements may apply.

        EventType type = event.getType();
        switch (type) {
            case SPEC_PROPOSED -> {
                requireMap(payload, "payload");
                requireArtifact(payload, "artifact");
            }
            case FILE_PATCH_PREVIEW -> {
                requireMap(payload, "payload");
                // Either patch or files must exist.
                Object patch = payload.get("patch");
                Object files = payload.get("files");
                if (patch == null && files == null) {
                    throw new ContractViolationException("FILE_PATCH_PREVIEW requires payload.patch or payload.files");
                }
            }
            case TOOL_START -> {
                requireMap(payload, "payload");
                requireString(payload, "tool");
            }
            case TOOL_END -> {
                requireMap(payload, "payload");
                requireString(payload, "tool");
                requireString(payload, "status");
            }
            case BUILD_STARTED -> requireMap(payload, "payload");
            case BUILD_LOG -> {
                requireMap(payload, "payload");
                requireString(payload, "message");
            }
            case BUILD_DONE -> requireMap(payload, "payload");
            case TASK_FAILED -> {
                requireMap(payload, "payload");
                requireString(payload, "reason");
            }
            case APPROVAL_REQUIRED -> {
                requireMap(payload, "payload");
                requireString(payload, "approvalId");
                requireApprovalContext(payload, "context");
            }
            case APPROVAL_RESULT -> {
                requireMap(payload, "payload");
                requireString(payload, "approvalId");
                // decision is required but cross-language casing differs; accept "decision" only.
                requireString(payload, "decision");
            }
            case DEPLOY_PLAN -> {
                requireMap(payload, "payload");
                requireString(payload, "requestId");
                requireString(payload, "environment");
                requireArtifact(payload, "artifact");
                if (payload.containsKey("context")) {
                    requireApprovalContext(payload, "context");
                }
            }
            case DEPLOY_RESULT -> {
                requireMap(payload, "payload");
                requireString(payload, "requestId");
                requireString(payload, "status");
                validateOptionalArtifact(payload, "resultArtifact");
            }
            case ARTIFACT_READY -> {
                requireMap(payload, "payload");
                requireArtifact(payload, "artifact");
            }
            default -> {
                // legacy/other events: no additional constraints here
            }
        }
    }

    private static void requireApprovalContext(Map<String, Object> payload, String key) {
        requireMap(payload, key);
        @SuppressWarnings("unchecked")
        Map<String, Object> ctx = (Map<String, Object>) payload.get(key);
        requireString(ctx, "action");
        requireString(ctx, "tool");
        requireString(ctx, "workspaceRef");
        requireString(ctx, "inputsHash");
    }

    private static void requireArtifact(Map<String, Object> payload, String key) {
        requireMap(payload, key);
        @SuppressWarnings("unchecked")
        Map<String, Object> artifact = (Map<String, Object>) payload.get(key);
        validateArtifactMap(artifact);
    }

    private static void validateOptionalArtifact(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return;
        }
        if (!(value instanceof Map)) {
            throw new ContractViolationException("payload." + key + " must be an object");
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> artifact = (Map<String, Object>) value;
        validateArtifactMap(artifact);
    }

    private static void validateArtifactMap(Map<String, Object> artifact) {
        requireString(artifact, "artifactId");
        requireString(artifact, "type");
        ArtifactMetadataContractValidator.validateNestedDescriptorsFromMap(artifact);
        // hash/size/mime are strongly recommended but optional for compatibility.
    }

    private static void requireMap(Map<String, Object> map, String name) {
        if (map == null) {
            throw new ContractViolationException(name + " is required");
        }
        // For nested map checks:
        if (!"payload".equals(name)) {
            Object value = map.get(name);
            if (!(value instanceof Map)) {
                throw new ContractViolationException("payload." + name + " must be an object");
            }
        }
    }

    private static void requireString(Map<String, Object> payload, String key) {
        if (payload == null) {
            throw new ContractViolationException("payload is required");
        }
        Object value = payload.get(key);
        if (!(value instanceof String) || isBlank((String) value)) {
            throw new ContractViolationException("payload." + key + " is required");
        }
    }

    private static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}

