/**
 * Agent-facing REST API for node registration, heartbeats, task polling, and event ingestion.
 */
package com.autocode.controlplane.api;

import com.autocode.controlplane.model.AgentNode;
import com.autocode.controlplane.service.AgentRegistryService;
import com.autocode.controlplane.service.TaskService;
import com.autocode.protocol.model.ApprovalDecision;
import com.autocode.protocol.model.TaskSummary;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/agent")
@Validated
public class AgentController {
    private final AgentRegistryService agentRegistryService;
    private final TaskService taskService;

    public AgentController(AgentRegistryService agentRegistryService, TaskService taskService) {
        this.agentRegistryService = agentRegistryService;
        this.taskService = taskService;
    }

    @PostMapping("/register")
    public ResponseEntity<ApiResponse<AgentNode>> register(@Valid @RequestBody AgentRegisterRequest request) {
        return ResponseEntity.ok(ApiResponse.ok(agentRegistryService.register(request)));
    }

    @PostMapping("/heartbeat")
    public ResponseEntity<ApiResponse<AgentNode>> heartbeat(@Valid @RequestBody AgentHeartbeatRequest request) {
        return ResponseEntity.ok(ApiResponse.ok(agentRegistryService.heartbeat(request)));
    }

    @GetMapping("/tasks/next")
    public ResponseEntity<ApiResponse<TaskSummary>> getNextTask(
            @RequestParam("nodeId")
            @NotBlank(message = "nodeId must not be blank")
            @Size(max = 64, message = "nodeId size must be between 0 and 64")
            String nodeId,
            @RequestParam(value = "profile", required = false) String profile
    ) {
        String normalizedNodeId = nodeId.trim();
        String normalizedProfile = profile == null ? null : profile.trim();
        if (normalizedProfile != null && normalizedProfile.isEmpty()) {
            normalizedProfile = null;
        }
        if (!agentRegistryService.isNodeRegistered(normalizedNodeId)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ApiResponse.error("node not registered"));
        }
        return taskService.pollNextTaskForNode(normalizedNodeId, normalizedProfile)
                .map(task -> ResponseEntity.ok(ApiResponse.ok(task)))
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @PostMapping("/tasks/{taskId}/events")
    public ResponseEntity<ApiResponse<TaskSummary>> ingestEvent(
            @PathVariable("taskId") String taskId,
            @Valid @RequestBody AgentEventRequest request
    ) {
        return taskService.ingestAgentEvent(taskId, request.getEvent())
                .map(summary -> ResponseEntity.ok(ApiResponse.ok(summary)))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @GetMapping("/tasks/{taskId}/approval")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getApprovalStatus(@PathVariable("taskId") String taskId) {
        if (!taskService.taskExists(taskId)) {
            return ResponseEntity.notFound().build();
        }
        ApprovalDecision decision = taskService.getApprovalDecision(taskId).orElse(ApprovalDecision.PENDING);
        return ResponseEntity.ok(ApiResponse.ok(Map.of("decision", decision.name().toLowerCase())));
    }

    @GetMapping("/nodes")
    public ResponseEntity<ApiResponse<List<AgentNode>>> listNodes() {
        return ResponseEntity.ok(ApiResponse.ok(agentRegistryService.listAgents()));
    }
}
