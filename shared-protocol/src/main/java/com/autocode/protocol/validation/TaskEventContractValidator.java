package com.autocode.protocol.validation;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;

import java.util.List;
import java.util.Locale;
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
            case TASK_CREATED -> {
                requireMap(payload, "payload");
                requireString(payload, "projectId");
            }
            case TASK_STARTED -> {
                requireMap(payload, "payload");
                requireString(payload, "nodeId");
            }
            case ASSISTANT_OUTPUT -> {
                requireMap(payload, "payload");
                requireString(payload, "message");
                validateAssistantOutputExtensions(payload);
            }
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
            case TASK_DONE -> {
                requireMap(payload, "payload");
                requireString(payload, "result");
            }
            case TASK_FAILED -> {
                requireMap(payload, "payload");
                requireString(payload, "reason");
                validateTaskFailedExtensions(payload);
            }
            case HEARTBEAT -> requireMap(payload, "payload");
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

    private static void validateAssistantOutputExtensions(Map<String, Object> payload) {
        validateOptionalIntent(payload, "intent");
        validateOptionalConfidence(payload, "confidence");
        validateOptionalBoolean(payload, "llmFallback");
        validateOptionalNonBlankString(payload, "reason");
        validateFixLoopFields(payload);
        validateReviewFields(payload);
    }

    private static void validateTaskFailedExtensions(Map<String, Object> payload) {
        validateFixLoopFields(payload);
        validateReviewFields(payload);
    }

    private static void validateFixLoopFields(Map<String, Object> payload) {
        Integer attempt = validateOptionalPositiveInt(payload, "attempt");
        Integer maxAttempts = validateOptionalPositiveInt(payload, "maxAttempts");
        validateOptionalNonBlankString(payload, "lastTestError");
        if (attempt != null && maxAttempts != null && attempt > maxAttempts) {
            throw new ContractViolationException("payload.attempt must be <= payload.maxAttempts");
        }
    }

    private static void validateReviewFields(Map<String, Object> payload) {
        Object riskLevel = payload.get("riskLevel");
        if (riskLevel != null) {
            if (!(riskLevel instanceof String riskText) || isBlank(riskText)) {
                throw new ContractViolationException("payload.riskLevel must be a non-blank string");
            }
            String normalized = riskText.trim().toLowerCase(Locale.ROOT);
            if (!normalized.equals("high") && !normalized.equals("medium") && !normalized.equals("low")) {
                throw new ContractViolationException("payload.riskLevel must be one of high|medium|low");
            }
        }

        Object issues = payload.get("issues");
        if (issues != null) {
            if (!(issues instanceof List<?> issueList)) {
                throw new ContractViolationException("payload.issues must be an array");
            }
            for (int i = 0; i < issueList.size(); i++) {
                Object item = issueList.get(i);
                if (!(item instanceof String issueText) || isBlank(issueText)) {
                    throw new ContractViolationException("payload.issues[" + i + "] must be a non-blank string");
                }
            }
        }
        validateOptionalNonBlankString(payload, "summary");
    }

    private static void validateOptionalIntent(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return;
        }
        if (!(value instanceof String intent) || isBlank(intent)) {
            throw new ContractViolationException("payload." + key + " must be a non-blank string");
        }
        String normalized = intent.trim().toLowerCase(Locale.ROOT);
        if (!normalized.equals("code_change")
                && !normalized.equals("deploy")
                && !normalized.equals("test")
                && !normalized.equals("analyze")) {
            throw new ContractViolationException("payload." + key + " must be one of code_change|deploy|test|analyze");
        }
    }

    private static void validateOptionalConfidence(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return;
        }
        if (!(value instanceof Number number)) {
            throw new ContractViolationException("payload." + key + " must be a number");
        }
        double confidence = number.doubleValue();
        if (Double.isNaN(confidence) || Double.isInfinite(confidence) || confidence < 0 || confidence > 1) {
            throw new ContractViolationException("payload." + key + " must be in [0,1]");
        }
    }

    private static void validateOptionalBoolean(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return;
        }
        if (!(value instanceof Boolean)) {
            throw new ContractViolationException("payload." + key + " must be a boolean");
        }
    }

    private static void validateOptionalNonBlankString(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return;
        }
        if (!(value instanceof String s) || isBlank(s)) {
            throw new ContractViolationException("payload." + key + " must be a non-blank string");
        }
    }

    private static Integer validateOptionalPositiveInt(Map<String, Object> payload, String key) {
        Object value = payload.get(key);
        if (value == null) {
            return null;
        }
        if (!(value instanceof Number number)) {
            throw new ContractViolationException("payload." + key + " must be an integer");
        }
        double asDouble = number.doubleValue();
        if (Double.isNaN(asDouble) || Double.isInfinite(asDouble) || asDouble != Math.rint(asDouble)) {
            throw new ContractViolationException("payload." + key + " must be an integer");
        }
        long asLong = number.longValue();
        if (asLong < 1 || asLong > Integer.MAX_VALUE) {
            throw new ContractViolationException("payload." + key + " must be >= 1");
        }
        return (int) asLong;
    }

    private static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}

