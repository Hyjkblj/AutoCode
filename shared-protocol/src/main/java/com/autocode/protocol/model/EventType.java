/**
 * MVP task event types used for state transitions and UI updates.
 */
package com.autocode.protocol.model;

public enum EventType {
    TASK_CREATED,
    TASK_STARTED,
    ASSISTANT_OUTPUT,
    TOOL_START,
    TOOL_END,
    FILE_PATCH_PREVIEW,
    APPROVAL_REQUIRED,
    APPROVAL_RESULT,
    TASK_DONE,
    TASK_FAILED,
    HEARTBEAT
}
