/**
 * Event Controller implementing explicit ACK protocol with Redis-based deduplication.
 * Validates Requirements 2.4 (Event ACK Protocol Compliance) and 2.5 (Event Deduplication).
 */
package com.autocode.event;

import com.autocode.controlplane.api.AgentEventRequest;
import com.autocode.controlplane.api.ApiResponse;
import com.autocode.controlplane.service.AgentRegistryService;
import com.autocode.controlplane.service.TaskService;
import com.autocode.controlplane.service.observability.ControlPlaneMetrics;
import com.autocode.protocol.model.AckErrorCode;
import com.autocode.protocol.model.EventAckResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.Duration;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/events")
@Validated
public class EventController {
    private static final Logger log = LoggerFactory.getLogger(EventController.class);

    private final TaskService taskService;
    private final StringRedisTemplate redisTemplate;
    private final EventDeduplicationService deduplicationService;
    private final AgentRegistryService agentRegistryService;
    private final ControlPlaneMetrics metrics;

    @Autowired
    public EventController(
            TaskService taskService,
            StringRedisTemplate redisTemplate,
            EventDeduplicationService deduplicationService,
            AgentRegistryService agentRegistryService,
            ControlPlaneMetrics metrics) {
        this.taskService = taskService;
        this.redisTemplate = redisTemplate;
        this.deduplicationService = deduplicationService;
        this.agentRegistryService = agentRegistryService;
        this.metrics = metrics;
    }

    /**
     * Enhanced event ingestion endpoint with explicit ACK protocol.
     * Returns ACK response with sequence number, acceptance status, and duplicate detection.
     */
    @PostMapping("/ingest")
    public ResponseEntity<ApiResponse<EventAckResponse>> ingestEventWithAck(
            @RequestParam("taskId")
            @NotBlank(message = "taskId must not be blank")
            @Size(max = 64, message = "taskId size must be between 0 and 64")
            String taskId,

            @RequestParam(value = "nodeId", required = false)
            @Size(max = 64, message = "nodeId size must be between 0 and 64")
            String nodeId,

            @Valid @RequestBody AgentEventRequest request
    ) {
        try {
            // Validate node registration if nodeId is provided
            String normalizedNodeId = null;
            if (nodeId != null) {
                normalizedNodeId = nodeId.trim();
                if (normalizedNodeId.isEmpty()) {
                    metrics.ackFailures.increment();
                    return ResponseEntity.badRequest()
                            .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.INVALID_NODE_ID)));
                }
                if (!agentRegistryService.isNodeRegistered(normalizedNodeId)) {
                    metrics.ackFailures.increment();
                    return ResponseEntity.status(HttpStatus.FORBIDDEN)
                            .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.NODE_NOT_REGISTERED)));
                }
            }

            String eventId = request.getEvent().getEventId();
            if (eventId == null || eventId.isBlank()) {
                metrics.ackFailures.increment();
                return ResponseEntity.badRequest()
                        .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.MISSING_EVENT_ID)));
            }

            // Check for duplicate event via Redis (fast path)
            boolean isDuplicate = deduplicationService.isDuplicate(eventId);
            if (isDuplicate) {
                log.debug("Duplicate event detected via Redis: {}", eventId);
                Long originalSeq = deduplicationService.getOriginalSequence(eventId);
                metrics.duplicateEvents.increment();
                return ResponseEntity.ok(ApiResponse.ok(
                        EventAckResponse.duplicate(originalSeq != null ? originalSeq : 0L)));
            }

            // Process the event — TaskService handles DB-level dedup
            Optional<TaskService.IngestResult> result = taskService.ingestAgentEvent(taskId, request.getEvent(), normalizedNodeId);

            if (result.isEmpty()) {
                metrics.ackFailures.increment();
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.TASK_NOT_FOUND)));
            }

            TaskService.IngestResult ingestResult = result.get();

            // If TaskService detected a DB-level duplicate, mark in Redis and return duplicate ACK
            if (ingestResult.duplicate()) {
                deduplicationService.markProcessed(eventId, ingestResult.assignedSeq());
                metrics.duplicateEvents.increment();
                return ResponseEntity.ok(ApiResponse.ok(EventAckResponse.duplicate(ingestResult.assignedSeq())));
            }

            // Mark as processed and store assigned sequence for future duplicate detection
            long assignedSeq = ingestResult.assignedSeq();
            deduplicationService.markProcessed(eventId, assignedSeq);

            log.debug("Event processed successfully: {} with seq: {}", eventId, assignedSeq);
            return ResponseEntity.ok(ApiResponse.ok(EventAckResponse.accepted(assignedSeq)));

        } catch (AccessDeniedException e) {
            log.warn("Access denied while processing event for task {}: {}", taskId, e.getMessage());
            metrics.ackFailures.increment();
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.ACCESS_DENIED)));
        } catch (IllegalStateException e) {
            log.warn("Illegal state transition for task {}: {}", taskId, e.getMessage());
            metrics.ackFailures.increment();
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.ILLEGAL_STATE_TRANSITION)));
        } catch (IllegalArgumentException e) {
            log.warn("Invalid event request for task {}: {}", taskId, e.getMessage());
            metrics.ackFailures.increment();
            return ResponseEntity.badRequest()
                    .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.INVALID_EVENT)));
        } catch (Exception e) {
            log.error("Error processing event for task {}: {}", taskId, e.getMessage(), e);
            metrics.ackFailures.increment();
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.ok(EventAckResponse.rejected(AckErrorCode.PROCESSING_ERROR)));
        }
    }

    /**
     * Health check endpoint for event processing
     */
    @GetMapping("/health")
    public ResponseEntity<ApiResponse<String>> health() {
        try {
            // Test Redis connectivity
            redisTemplate.opsForValue().set("health:check", "ok", Duration.ofSeconds(10));
            String result = redisTemplate.opsForValue().get("health:check");

            if ("ok".equals(result)) {
                return ResponseEntity.ok(ApiResponse.ok("Event processing healthy"));
            } else {
                return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                        .body(ApiResponse.error("Redis connectivity issue"));
            }
        } catch (Exception e) {
            log.error("Health check failed: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(ApiResponse.error("Event processing unhealthy: " + e.getMessage()));
        }
    }
}
