package com.autocode.event;

import com.autocode.protocol.model.AckErrorCode;
import com.autocode.protocol.model.EventAckResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Service for processing and persisting events.
 * Implements Requirements 2.4, 2.5, 2.6 (Event processing, deduplication, sequence continuity).
 */
@Service
public class EventProcessingService {
    private static final Logger log = LoggerFactory.getLogger(EventProcessingService.class);
    
    private final EventRepository eventRepository;
    private final EventDeduplicationService deduplicationService;
    private final ObjectMapper objectMapper;

    @Autowired
    public EventProcessingService(
            EventRepository eventRepository,
            EventDeduplicationService deduplicationService,
            ObjectMapper objectMapper) {
        this.eventRepository = eventRepository;
        this.deduplicationService = deduplicationService;
        this.objectMapper = objectMapper;
    }

    /**
     * Process an incoming event with deduplication and persistence.
     * 
     * @param eventId the event ID
     * @param taskId the task ID
     * @param sessionId the session ID
     * @param assistant the assistant identifier
     * @param eventType the event type
     * @param timestamp the event timestamp
     * @param payload the event payload
     * @param seq the sequence number
     * @param eventVersion the event version
     * @param nodeId the node ID (optional)
     * @return EventAckResponse with processing result
     */
    @Transactional
    public EventAckResponse processEvent(
            String eventId,
            String taskId,
            String sessionId,
            String assistant,
            String eventType,
            Instant timestamp,
            Map<String, Object> payload,
            long seq,
            int eventVersion,
            String nodeId) {
        
        // Validate event ID
        if (eventId == null || eventId.isBlank()) {
            return EventAckResponse.rejected(AckErrorCode.MISSING_EVENT_ID);
        }

        // Check for duplicate
        boolean isDuplicate = deduplicationService.isDuplicate(eventId);
        if (isDuplicate) {
            log.debug("Duplicate event detected: {}", eventId);
            Long originalSeq = deduplicationService.getOriginalSequence(eventId);
            return EventAckResponse.duplicate(originalSeq != null ? originalSeq : 0L);
        }

        try {
            // Create and persist event entity
            EventEntity entity = new EventEntity();
            entity.setEventId(eventId);
            entity.setTaskId(taskId);
            entity.setSessionId(sessionId);
            entity.setAssistant(assistant);
            entity.setEventType(eventType);
            entity.setEventTimestamp(timestamp);
            entity.setSeqNum(seq);
            entity.setEventVersion(eventVersion);
            entity.setNodeId(nodeId);

            // Serialize payload to JSON
            if (payload != null && !payload.isEmpty()) {
                try {
                    entity.setPayloadJson(objectMapper.writeValueAsString(payload));
                } catch (JsonProcessingException e) {
                    log.error("Error serializing payload for event {}: {}", eventId, e.getMessage());
                    return EventAckResponse.rejected(AckErrorCode.PROCESSING_ERROR);
                }
            }

            // Save to database
            eventRepository.save(entity);

            // Mark as processed in deduplication service
            deduplicationService.markProcessed(eventId, seq);

            log.debug("Event processed successfully: {} with seq: {}", eventId, seq);

            return EventAckResponse.accepted(seq);

        } catch (Exception e) {
            log.error("Error processing event {}: {}", eventId, e.getMessage(), e);
            return EventAckResponse.rejected(AckErrorCode.PROCESSING_ERROR);
        }
    }

    /**
     * Get all events for a task.
     */
    public List<EventEntity> getEventsByTask(String taskId) {
        return eventRepository.findByTaskIdOrderBySeqNumAsc(taskId);
    }

    /**
     * Get the latest event for a task.
     */
    public Optional<EventEntity> getLatestEvent(String taskId) {
        return eventRepository.findFirstByTaskIdOrderBySeqNumDesc(taskId);
    }

    /**
     * Get the maximum sequence number for a task.
     */
    public Optional<Long> getMaxSequenceNumber(String taskId) {
        return eventRepository.findMaxSeqNumByTaskId(taskId);
    }

    /**
     * Count events for a task.
     */
    public long countEvents(String taskId) {
        return eventRepository.countByTaskId(taskId);
    }

    /**
     * Check if an event exists.
     */
    public boolean eventExists(String eventId) {
        return eventRepository.existsByEventId(eventId);
    }
}
