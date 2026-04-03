/**
 * Operator-facing task REST API (create/query/events/approval/cancel/artifacts).
 */
package com.autocode.controlplane.api;

import com.autocode.controlplane.service.TaskService;
import com.autocode.controlplane.service.ArtifactQueryService;
import com.autocode.protocol.model.TaskEvent;
import com.autocode.protocol.model.TaskSummary;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/tasks")
public class TaskController {
    private final TaskService taskService;
    private final ArtifactQueryService artifactQueryService;

    public TaskController(TaskService taskService, ArtifactQueryService artifactQueryService) {
        this.taskService = taskService;
        this.artifactQueryService = artifactQueryService;
    }

    @PostMapping
    // Use #p1 instead of named params to avoid requiring Java -parameters for SpEL.
    @PreAuthorize("@projectAuthz.canAccessProject(#p1.projectId)")
    public ResponseEntity<ApiResponse<TaskSummary>> createTask(
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody CreateTaskRequest request
    ) {
        TaskSummary summary = taskService.createTask(request, idempotencyKey);
        return ResponseEntity.ok(ApiResponse.ok(summary));
    }

    @GetMapping("/{taskId}")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<ApiResponse<TaskSummary>> getTask(@PathVariable("taskId") String taskId) {
        return taskService.getTaskSummary(taskId)
                .map(summary -> ResponseEntity.ok(ApiResponse.ok(summary)))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @GetMapping("/{taskId}/events")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<ApiResponse<List<TaskEvent>>> getTaskEvents(
            @PathVariable("taskId") String taskId,
            @RequestParam(value = "lastSeq", required = false) Long lastSeq,
            @RequestParam(value = "lastEventId", required = false) Long lastEventId
    ) {
        // Backward compatible: lastEventId was previously used as lastSeq.
        Long effective = lastSeq != null ? lastSeq : lastEventId;
        List<TaskEvent> events = taskService.getTaskEvents(taskId, effective);
        return ResponseEntity.ok(ApiResponse.ok(events));
    }

    @PostMapping("/{taskId}/approval")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<ApiResponse<TaskSummary>> approveTask(
            @PathVariable("taskId") String taskId,
            @Valid @RequestBody ApprovalDecisionRequest request
    ) {
        return taskService.applyApproval(taskId, request)
                .map(summary -> ResponseEntity.ok(ApiResponse.ok(summary)))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping("/{taskId}/cancel")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<ApiResponse<TaskSummary>> cancelTask(@PathVariable("taskId") String taskId) {
        return taskService.cancelTask(taskId, "user_cancel")
                .map(summary -> ResponseEntity.ok(ApiResponse.ok(summary)))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    /**
     * Derived artifacts (patch previews + audit logs) aggregated from persisted events for UI.
     * Note: This is distinct from "uploaded artifacts" (zip exports, build reports, etc.).
     */
    @GetMapping("/{taskId}/artifacts/derived")
    @PreAuthorize("@projectAuthz.canAccessTask(#p0)")
    public ResponseEntity<ApiResponse<TaskArtifactsResponse>> getDerivedArtifacts(@PathVariable("taskId") String taskId) {
        TaskArtifactsResponse response = artifactQueryService.getArtifacts(taskId);
        return ResponseEntity.ok(ApiResponse.ok(response));
    }
}
