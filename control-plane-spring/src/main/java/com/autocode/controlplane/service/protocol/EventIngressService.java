package com.autocode.controlplane.service.protocol;

import com.autocode.controlplane.service.TaskService;
import com.autocode.controlplane.service.audit.AuditService;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskStatus;
import com.autocode.protocol.model.TaskSummary;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Optional;

/**
 * Event ingress boundary: validates, normalizes, and delegates event ingestion.
 *
 * <p>This service sits between the HTTP/ACK layer ({@code EventController})
 * and the task state management ({@code TaskService}). It owns the "is this
 * event acceptable?" question, while TaskService owns "what does this event
 * do to the task state?"</p>
 *
 * <p>Responsibilities:
 * <ul>
 *   <li>Pre-ingestion validation (event structure, nodeId assignment)</li>
 *   <li>Delegation to TaskService for state transitions and persistence</li>
 *   <li>Post-ingestion audit logging for approval context mismatches</li>
 * </ul>
 */
@Service
public class EventIngressService {

    private final TaskService taskService;
    private final TaskEventValidator eventValidator;
    private final AuditService auditService;

    public EventIngressService(
            TaskService taskService,
            TaskEventValidator eventValidator,
            AuditService auditService
    ) {
        this.taskService = taskService;
        this.eventValidator = eventValidator;
        this.auditService = auditService;
    }

    /**
     * Ingest an agent event into the task lifecycle.
     *
     * @param taskId the target task
     * @param event  the event to ingest
     * @param nodeId the reporting agent node (may be null)
     * @return ingest result with assigned seq and duplicate flag, or empty if task not found
     */
    public Optional<TaskService.IngestResult> ingest(String taskId, TaskEvent event, String nodeId) {
        eventValidator.validateOrThrow(event);
        Optional<TaskService.IngestResult> result = taskService.ingestAgentEvent(taskId, event, nodeId);

        if (result.isPresent() && !result.get().duplicate()) {
            auditApprovalContextMismatch(taskId, event);
        }

        return result;
    }

    /**
     * Convenience overload without nodeId.
     */
    public Optional<TaskSummary> ingest(String taskId, TaskEvent event) {
        return ingest(taskId, event, null).map(TaskService.IngestResult::summary);
    }

    private void auditApprovalContextMismatch(String taskId, TaskEvent event) {
        if (event.getPayload() == null) {
            return;
        }
        if (!Boolean.TRUE.equals(event.getPayload().get("approvalContextMismatch"))) {
            return;
        }
        auditService.log(taskId, "control-plane", "approval.context.mismatch", Map.of(
                "expected", event.getPayload().get("expectedApprovalContext"),
                "actual", event.getPayload().get("actualApprovalContext")
        ));
    }
}
