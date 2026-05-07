package com.autocode.event;

import com.autocode.protocol.model.AckErrorCode;
import com.autocode.protocol.model.EventAckResponse;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * REST controller for the Event Service.
 *
 * Endpoints:
 *  POST /events/ingest       — ingest event with ACK protocol
 *  GET  /events/task/{taskId} — retrieve events for a task
 *  GET  /events/health       — health check
 *
 * Requirements: 2.4, 2.5, 2.6, 11.1
 */
@RestController
@RequestMapping("/events")
@Validated
public class EventController {
    private static final Logger log = LoggerFactory.getLogger(EventController.class);

    private final EventProcessingService processingService;
    private final StringRedisTemplate redisTemplate;

    @Autowired
    public EventController(
            EventProcessingService processingService,
            StringRedisTemplate redisTemplate) {
        this.processingService = processingService;
        this.redisTemplate = redisTemplate;
    }

    /**
     * Enhanced event ingestion endpoint with explicit ACK protocol.
     * Returns ACK response with sequence number, acceptance status, and duplicate detection.
     *
     * Requirements: 2.4 (Event ACK Protocol Compliance), 2.5 (Event Deduplication)
     */
    @PostMapping("/ingest")
    public ResponseEntity<EventAckResponse> ingestEventWithAck(
            @RequestParam("taskId")
            @NotBlank(message = "taskId must not be blank")
            @Size(max = 64, message = "taskId size must be between 0 and 64")
            String taskId,

            @RequestParam(value = "nodeId", required = false)
            @Size(max = 64, message = "nodeId size must be between 0 and 64")
            String nodeId,

            @RequestBody Map<String, Object> requestBody
    ) {
        try {
            // Extract event data from request body
            @SuppressWarnings("unchecked")
            Map<String, Object> eventData = (Map<String, Object>) requestBody.get("event");

            if (eventData == null) {
                return ResponseEntity.badRequest()
                        .body(EventAckResponse.rejected(AckErrorCode.INVALID_EVENT));
            }

            // Extract event fields
            String eventId = (String) eventData.get("eventId");
            String sessionId = (String) eventData.get("sessionId");
            String assistant = (String) eventData.get("assistant");
            String eventType = (String) eventData.get("type");

            // Parse timestamp
            Instant timestamp = Instant.now();
            if (eventData.get("timestamp") != null) {
                try {
                    timestamp = Instant.parse(eventData.get("timestamp").toString());
                } catch (Exception e) {
                    log.warn("Failed to parse timestamp, using current time: {}", e.getMessage());
                }
            }

            // Extract payload
            @SuppressWarnings("unchecked")
            Map<String, Object> payload = (Map<String, Object>) eventData.get("payload");
            if (payload == null) {
                payload = new HashMap<>();
            }

            // Extract sequence number
            long seq = 0L;
            if (eventData.get("seq") != null) {
                seq = ((Number) eventData.get("seq")).longValue();
            }

            // Extract event version
            int eventVersion = 1;
            if (eventData.get("eventVersion") != null) {
                eventVersion = ((Number) eventData.get("eventVersion")).intValue();
            }

            // Validate node ID if provided
            String normalizedNodeId = null;
            if (nodeId != null) {
                normalizedNodeId = nodeId.trim();
                if (normalizedNodeId.isEmpty()) {
                    return ResponseEntity.badRequest()
                            .body(EventAckResponse.rejected(AckErrorCode.INVALID_NODE_ID));
                }
            }

            // Process the event
            EventAckResponse ackResponse = processingService.processEvent(
                    eventId, taskId, sessionId, assistant, eventType,
                    timestamp, payload, seq, eventVersion, normalizedNodeId
            );

            // Determine HTTP status based on ACK response
            if (!ackResponse.isAccepted()) {
                if (AckErrorCode.MISSING_EVENT_ID.name().equals(ackResponse.getErrorCode())) {
                    return ResponseEntity.badRequest().body(ackResponse);
                }
                return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(ackResponse);
            }

            return ResponseEntity.ok(ackResponse);

        } catch (Exception e) {
            log.error("Error processing event for task {}: {}", taskId, e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(EventAckResponse.rejected(AckErrorCode.PROCESSING_ERROR));
        }
    }

    /**
     * Retrieve all events for a specific task.
     *
     * @param taskId the task ID
     * @return list of events ordered by sequence number
     */
    @GetMapping("/task/{taskId}")
    public ResponseEntity<Map<String, Object>> getEventsByTask(
            @PathVariable("taskId") String taskId) {
        try {
            List<EventEntity> events = processingService.getEventsByTask(taskId);

            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("taskId", taskId);
            response.put("count", events.size());
            response.put("events", events);

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("Error retrieving events for task {}: {}", taskId, e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("success", false, "error", e.getMessage()));
        }
    }

    /**
     * Health check endpoint for event processing.
     *
     * @return health status
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        try {
            // Test Redis connectivity
            redisTemplate.opsForValue().set("health:check", "ok", Duration.ofSeconds(10));
            String result = redisTemplate.opsForValue().get("health:check");

            if ("ok".equals(result)) {
                return ResponseEntity.ok(Map.of(
                        "success", true,
                        "status", "healthy",
                        "message", "Event processing healthy"
                ));
            } else {
                return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                        .body(Map.of(
                                "success", false,
                                "status", "unhealthy",
                                "message", "Redis connectivity issue"
                        ));
            }
        } catch (Exception e) {
            log.error("Health check failed: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(Map.of(
                            "success", false,
                            "status", "unhealthy",
                            "message", "Event processing unhealthy: " + e.getMessage()
                    ));
        }
    }
}
