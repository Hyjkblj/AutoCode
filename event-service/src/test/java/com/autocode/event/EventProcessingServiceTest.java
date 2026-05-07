package com.autocode.event;

import com.autocode.protocol.model.EventAckResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Unit tests for EventProcessingService.
 * Validates Requirements 2.4, 2.5, 2.6 (Event processing, deduplication, sequence continuity).
 */
@ExtendWith(MockitoExtension.class)
class EventProcessingServiceTest {

    @Mock
    private EventRepository eventRepository;

    @Mock
    private EventDeduplicationService deduplicationService;

    private EventProcessingService service;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        service = new EventProcessingService(eventRepository, deduplicationService, objectMapper);
    }

    @Test
    void testProcessEvent_Success() {
        // Given
        String eventId = "evt_123";
        String taskId = "task_456";
        String sessionId = "session_789";
        String assistant = "coder";
        String eventType = "TASK_STARTED";
        Instant timestamp = Instant.now();
        Map<String, Object> payload = new HashMap<>();
        payload.put("key", "value");
        long seq = 1L;
        int eventVersion = 1;
        String nodeId = "node_001";

        when(deduplicationService.isDuplicate(eventId)).thenReturn(false);
        when(eventRepository.save(any(EventEntity.class))).thenAnswer(i -> i.getArgument(0));

        // When
        EventAckResponse response = service.processEvent(
            eventId, taskId, sessionId, assistant, eventType,
            timestamp, payload, seq, eventVersion, nodeId
        );

        // Then
        assertTrue(response.isAccepted());
        assertFalse(response.isDuplicate());
        assertNull(response.getErrorCode());
        assertEquals(seq, response.getSequenceNumber());

        // Verify entity was saved
        ArgumentCaptor<EventEntity> entityCaptor = ArgumentCaptor.forClass(EventEntity.class);
        verify(eventRepository).save(entityCaptor.capture());
        EventEntity savedEntity = entityCaptor.getValue();
        assertEquals(eventId, savedEntity.getEventId());
        assertEquals(taskId, savedEntity.getTaskId());
        assertEquals(sessionId, savedEntity.getSessionId());
        assertEquals(assistant, savedEntity.getAssistant());
        assertEquals(eventType, savedEntity.getEventType());
        assertEquals(seq, savedEntity.getSeqNum());
        assertEquals(eventVersion, savedEntity.getEventVersion());
        assertEquals(nodeId, savedEntity.getNodeId());

        // Verify deduplication was marked
        verify(deduplicationService).markProcessed(eventId, seq);
    }

    @Test
    void testProcessEvent_Duplicate() {
        // Given
        String eventId = "evt_123";
        long originalSeq = 42L;
        when(deduplicationService.isDuplicate(eventId)).thenReturn(true);
        when(deduplicationService.getOriginalSequence(eventId)).thenReturn(originalSeq);

        // When
        EventAckResponse response = service.processEvent(
            eventId, "task_456", "session_789", "coder", "TASK_STARTED",
            Instant.now(), new HashMap<>(), 1L, 1, null
        );

        // Then
        assertTrue(response.isAccepted());
        assertTrue(response.isDuplicate());
        assertNull(response.getErrorCode());
        assertEquals(originalSeq, response.getSequenceNumber());

        // Verify no save occurred
        verify(eventRepository, never()).save(any());
        verify(deduplicationService, never()).markProcessed(anyString(), anyLong());
    }

    @Test
    void testProcessEvent_MissingEventId() {
        // When
        EventAckResponse response = service.processEvent(
            null, "task_456", "session_789", "coder", "TASK_STARTED",
            Instant.now(), new HashMap<>(), 1L, 1, null
        );

        // Then
        assertFalse(response.isAccepted());
        assertFalse(response.isDuplicate());
        assertEquals("MISSING_EVENT_ID", response.getErrorCode());
        assertEquals(0L, response.getSequenceNumber());

        // Verify no processing occurred
        verify(deduplicationService, never()).isDuplicate(anyString());
        verify(eventRepository, never()).save(any());
    }

    @Test
    void testProcessEvent_BlankEventId() {
        // When
        EventAckResponse response = service.processEvent(
            "  ", "task_456", "session_789", "coder", "TASK_STARTED",
            Instant.now(), new HashMap<>(), 1L, 1, null
        );

        // Then
        assertFalse(response.isAccepted());
        assertFalse(response.isDuplicate());
        assertEquals("MISSING_EVENT_ID", response.getErrorCode());
    }

    @Test
    void testProcessEvent_EmptyPayload() {
        // Given
        String eventId = "evt_123";
        when(deduplicationService.isDuplicate(eventId)).thenReturn(false);
        when(eventRepository.save(any(EventEntity.class))).thenAnswer(i -> i.getArgument(0));

        // When
        EventAckResponse response = service.processEvent(
            eventId, "task_456", "session_789", "coder", "TASK_STARTED",
            Instant.now(), null, 1L, 1, null
        );

        // Then
        assertTrue(response.isAccepted());
        assertFalse(response.isDuplicate());
        assertNull(response.getErrorCode());

        // Verify entity was saved with null payload
        ArgumentCaptor<EventEntity> entityCaptor = ArgumentCaptor.forClass(EventEntity.class);
        verify(eventRepository).save(entityCaptor.capture());
        EventEntity savedEntity = entityCaptor.getValue();
        assertNull(savedEntity.getPayloadJson());
    }

    @Test
    void testProcessEvent_RepositoryException() {
        // Given
        String eventId = "evt_123";
        when(deduplicationService.isDuplicate(eventId)).thenReturn(false);
        when(eventRepository.save(any(EventEntity.class)))
            .thenThrow(new RuntimeException("Database error"));

        // When
        EventAckResponse response = service.processEvent(
            eventId, "task_456", "session_789", "coder", "TASK_STARTED",
            Instant.now(), new HashMap<>(), 1L, 1, null
        );

        // Then
        assertFalse(response.isAccepted());
        assertFalse(response.isDuplicate());
        assertEquals("PROCESSING_ERROR", response.getErrorCode());
        assertEquals(0L, response.getSequenceNumber());

        // Verify deduplication was not marked
        verify(deduplicationService, never()).markProcessed(anyString(), anyLong());
    }

    @Test
    void testEventExists() {
        // Given
        String eventId = "evt_123";
        when(eventRepository.existsByEventId(eventId)).thenReturn(true);

        // When
        boolean result = service.eventExists(eventId);

        // Then
        assertTrue(result);
        verify(eventRepository).existsByEventId(eventId);
    }

    @Test
    void testCountEvents() {
        // Given
        String taskId = "task_456";
        when(eventRepository.countByTaskId(taskId)).thenReturn(5L);

        // When
        long result = service.countEvents(taskId);

        // Then
        assertEquals(5L, result);
        verify(eventRepository).countByTaskId(taskId);
    }
}
