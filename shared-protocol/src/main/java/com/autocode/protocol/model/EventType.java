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
    SPEC_PROPOSED,
    BUILD_STARTED,
    BUILD_LOG,
    BUILD_DONE,
    APPROVAL_REQUIRED,
    APPROVAL_RESULT,
    DEPLOY_PLAN,
    DEPLOY_RESULT,
    ARTIFACT_READY,
    TASK_DONE,
    TASK_FAILED,
    HEARTBEAT
}
