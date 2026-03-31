package com.autocode.controlplane.service.protocol;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class TaskEventValidator {
    public static final int CURRENT_EVENT_VERSION = 1;

    public void validateOrThrow(TaskEvent event) {
        if (event == null) {
            throw new ProtocolValidationException("event is required");
        }
        if (event.getEventId() == null || event.getEventId().isBlank()) {
            throw new ProtocolValidationException("event.eventId is required");
        }
        if (event.getType() == null) {
            throw new ProtocolValidationException("event.type is required");
        }
        if (event.getAssistant() == null || event.getAssistant().isBlank()) {
            throw new ProtocolValidationException("event.assistant is required");
        }
        if (event.getEventVersion() <= 0) {
            // Accept legacy defaults as v1; anything else is invalid.
            event.setEventVersion(CURRENT_EVENT_VERSION);
        }
        if (event.getEventVersion() != CURRENT_EVENT_VERSION) {
            throw new ProtocolValidationException("unsupported eventVersion: " + event.getEventVersion());
        }
        if (event.getPayload() == null) {
            // Normalize; downstream expects non-null.
            event.setPayload(Map.of());
        }

        // Type-specific required fields
        if (event.getType() == EventType.APPROVAL_REQUIRED) {
            requireString(event.getPayload(), "approvalId");
            requireString(event.getPayload(), "action");
            requireString(event.getPayload(), "command");
        } else if (event.getType() == EventType.TOOL_START) {
            requireString(event.getPayload(), "tool");
        } else if (event.getType() == EventType.TOOL_END) {
            requireString(event.getPayload(), "tool");
        } else if (event.getType() == EventType.FILE_PATCH_PREVIEW) {
            // Backward compatible: older clients send file/added/removed; newer clients may send a full patch string.
            boolean hasPatch = hasNonBlankString(event.getPayload(), "patch");
            boolean hasFile = hasNonBlankString(event.getPayload(), "file");
            if (!hasPatch && !hasFile) {
                throw new ProtocolValidationException("event.payload.patch or event.payload.file is required");
            }
        } else if (event.getType() == EventType.TASK_FAILED) {
            requireString(event.getPayload(), "reason");
        }
    }

    private static void requireString(Map<String, Object> payload, String key) {
        Object v = payload.get(key);
        if (!(v instanceof String) || ((String) v).isBlank()) {
            throw new ProtocolValidationException("event.payload." + key + " is required");
        }
    }

    private static boolean hasNonBlankString(Map<String, Object> payload, String key) {
        Object v = payload.get(key);
        return (v instanceof String) && !((String) v).isBlank();
    }
}

