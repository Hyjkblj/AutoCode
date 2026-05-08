package com.autocode.controlplane.service.protocol;

import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskStatus;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Set;

/**
 * Defines the legal state transition table for the task lifecycle.
 *
 * <p>Extracted from TaskService for independent testability. The transition
 * rules are:</p>
 * <ul>
 *   <li>Informational events (ASSISTANT_OUTPUT, TOOL_START, etc.) are allowed
 *       from any active (non-terminal) state.</li>
 *   <li>Terminal states (DONE, FAILED, CANCELED) only accept HEARTBEAT.</li>
 *   <li>State-changing events follow the explicit transition table.</li>
 * </ul>
 */
@Component
public class TaskStateMachine {

    private static final Set<TaskStatus> TERMINAL = Set.of(
            TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELED
    );

    private static final Set<EventType> INFORMATIONAL = Set.of(
            EventType.ASSISTANT_OUTPUT,
            EventType.TOOL_START,
            EventType.TOOL_END,
            EventType.FILE_PATCH_PREVIEW,
            EventType.SPEC_PROPOSED,
            EventType.BUILD_STARTED,
            EventType.BUILD_LOG,
            EventType.BUILD_DONE,
            EventType.ARTIFACT_READY,
            EventType.HEARTBEAT
    );

    /**
     * State-changing event → set of allowed source statuses.
     */
    private static final Map<EventType, Set<TaskStatus>> TRANSITION_TABLE = Map.ofEntries(
            Map.entry(EventType.TASK_STARTED, Set.of(TaskStatus.QUEUED)),
            Map.entry(EventType.TASK_DONE, Set.of(TaskStatus.RUNNING)),
            Map.entry(EventType.TASK_FAILED, Set.of(TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL)),
            Map.entry(EventType.APPROVAL_REQUIRED, Set.of(TaskStatus.RUNNING)),
            Map.entry(EventType.APPROVAL_RESULT, Set.of(TaskStatus.WAITING_APPROVAL)),
            Map.entry(EventType.DEPLOY_PLAN, Set.of(TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL)),
            Map.entry(EventType.DEPLOY_RESULT, Set.of(TaskStatus.RUNNING))
    );

    /**
     * Whether the given status is a terminal (irreversible) state.
     */
    public boolean isTerminal(TaskStatus status) {
        return TERMINAL.contains(status);
    }

    /**
     * Whether the event is informational (carries data but doesn't change status).
     */
    public boolean isInformationalEvent(EventType eventType) {
        return INFORMATIONAL.contains(eventType);
    }

    /**
     * Whether an event type is allowed when the task is already in a terminal state.
     * Only HEARTBEAT is permitted for liveness signals.
     */
    public boolean isAllowedFromTerminal(EventType eventType) {
        return eventType == EventType.HEARTBEAT;
    }

    /**
     * Validates whether a state transition is legal.
     *
     * @return a {@link TransitionResult} describing whether the transition is
     *         allowed and, if not, why not
     */
    public TransitionResult validate(TaskStatus current, EventType eventType) {
        if (isTerminal(current)) {
            if (isAllowedFromTerminal(eventType)) {
                return TransitionResult.allowed();
            }
            return TransitionResult.rejected(
                    "event " + eventType + " not allowed in terminal state " + current);
        }

        if (isInformationalEvent(eventType)) {
            return TransitionResult.allowed();
        }

        Set<TaskStatus> allowedSources = TRANSITION_TABLE.get(eventType);
        if (allowedSources == null) {
            // Unknown event type — allow for forward compatibility
            return TransitionResult.allowed();
        }

        if (allowedSources.contains(current)) {
            return TransitionResult.allowed();
        }

        return TransitionResult.rejected(
                "illegal state transition: " + current + " + " + eventType);
    }

    /**
     * Result of a transition validation.
     */
    public record TransitionResult(boolean isAllowed, String rejectionReason) {
        public static TransitionResult allowed() {
            return new TransitionResult(true, null);
        }

        public static TransitionResult rejected(String reason) {
            return new TransitionResult(false, reason);
        }
    }
}
