/**
 * Event Controller implementing explicit ACK protocol with Redis-based deduplication.
 * Validates Requirements 2.4 (Event ACK Protocol Compliance) and 2.5 (Event Deduplication).
 */
package com.autocode.event;

import com.autocode.controlplane.api.AgentEventRequest;
import com.autocode.controlplane.api.ApiResponse;
import com.autocode.controlplane.service.AgentRegistryService;
import com.autocode.controlplane.service.TaskService;
import com.autocode.protocol.model.TaskSummary;
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
    
    // Redis key prefix for event deduplication
    private static final String DEDUP_KEY_PREFIX = "event:dedup:";
    
    // TTL for deduplication entries (24 hours)
    private static final Duration DEDUP_TTL = Duration.ofHours(24);
    
    private final TaskService taskService;
    private final StringRedisTemplate redisTemplate;
    private final EventDeduplicationService deduplicationService;
    private final AgentRegistryService agentRegistryService;

    @Autowired
    public EventController(
            TaskService taskService, 
            StringRedisTemplate redisTemplate,
            EventDeduplicationService deduplicationService,
            AgentRegistryService agentRegistryService) {
        this.taskService = taskService;
        this.redisTemplate = redisTemplate;
        this.deduplicationService = deduplicationService;
        this.agentRegistryService = agentRegistryService;
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
                    EventAckResponse ackResponse = new EventAckResponse(
                        0L, false, false, "INVALID_NODE_ID"
                    );
                    return ResponseEntity.badRequest()
                            .body(ApiResponse.ok(ackResponse));
                }
                if (!agentRegistryService.isNodeRegistered(normalizedNodeId)) {
                    EventAckResponse ackResponse = new EventAckResponse(
                        0L, false, false, "NODE_NOT_REGISTERED"
                    );
                    return ResponseEntity.status(HttpStatus.FORBIDDEN)
                            .body(ApiResponse.ok(ackResponse));
                }
            }

            String eventId = request.getEvent().getEventId();
            if (eventId == null || eventId.isBlank()) {
                EventAckResponse ackResponse = new EventAckResponse(
                    0L, false, false, "MISSING_EVENT_ID"
                );
                return ResponseEntity.badRequest()
                        .body(ApiResponse.ok(ackResponse));
            }

            // Check for duplicate event
            boolean isDuplicate = deduplicationService.isDuplicate(eventId);
            if (isDuplicate) {
                log.debug("Duplicate event detected: {}", eventId);
                
                // For duplicates, we still need to return an ACK with the original sequence
                Long originalSeq = deduplicationService.getOriginalSequence(eventId);
                EventAckResponse ackResponse = new EventAckResponse(
                    originalSeq != null ? originalSeq : 0L,
                    true,  // accepted (was already processed)
                    true,  // duplicate
                    null   // no error
                );
                
                return ResponseEntity.ok(ApiResponse.ok(ackResponse));
            }

            // Process the event
            Optional<TaskSummary> result = taskService.ingestAgentEvent(taskId, request.getEvent(), normalizedNodeId);
            
            if (result.isEmpty()) {
                EventAckResponse ackResponse = new EventAckResponse(
                    0L,
                    false,  // not accepted
                    false,  // not duplicate
                    "TASK_NOT_FOUND"
                );
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.ok(ackResponse));
            }

            // Mark as processed and store sequence for future duplicate detection
            long sequenceNumber = request.getEvent().getSeq();
            deduplicationService.markProcessed(eventId, sequenceNumber);

            // Return successful ACK
            EventAckResponse ackResponse = new EventAckResponse(
                sequenceNumber,
                true,   // accepted
                false,  // not duplicate
                null    // no error
            );

            log.debug("Event processed successfully: {} with seq: {}", eventId, sequenceNumber);
            return ResponseEntity.ok(ApiResponse.ok(ackResponse));

        } catch (AccessDeniedException e) {
            log.warn("Access denied while processing event for task {}: {}", taskId, e.getMessage());

            EventAckResponse ackResponse = new EventAckResponse(
                0L,
                false,
                false,
                "ACCESS_DENIED"
            );

            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ApiResponse.ok(ackResponse));
        } catch (IllegalArgumentException e) {
            log.warn("Invalid event request for task {}: {}", taskId, e.getMessage());

            EventAckResponse ackResponse = new EventAckResponse(
                0L,
                false,
                false,
                "INVALID_EVENT"
            );

            return ResponseEntity.badRequest()
                    .body(ApiResponse.ok(ackResponse));
        } catch (Exception e) {
            log.error("Error processing event for task {}: {}", taskId, e.getMessage(), e);
            
            EventAckResponse ackResponse = new EventAckResponse(
                0L,
                false,  // not accepted
                false,  // not duplicate
                "PROCESSING_ERROR"
            );
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.ok(ackResponse));
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
