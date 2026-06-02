/**
 * Integration test for Event ACK Protocol compliance.
 * Validates Requirements 2.4 (Event ACK Protocol Compliance) and 2.5 (Event Deduplication).
 */
package com.autocode.event;

import com.autocode.controlplane.api.AgentEventRequest;
import com.autocode.protocol.model.EventType;
import com.autocode.protocol.model.TaskEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureWebMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.HashMap;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureWebMvc
@ActiveProfiles("test")
@Transactional
class EventAckProtocolIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @Autowired
    private EventDeduplicationService deduplicationService;

    private TaskEvent testEvent;
    private AgentEventRequest testRequest;

    @BeforeEach
    void setUp() {
        // Clean up Redis before each test
        redisTemplate.getConnectionFactory().getConnection().flushDb();

        testEvent = new TaskEvent();
        testEvent.setEventId("evt_integration_test_" + System.currentTimeMillis());
        testEvent.setTaskId("tsk_test123");
        testEvent.setType(EventType.TASK_STARTED);
        testEvent.setTimestamp(Instant.now());
        testEvent.setSeq(1L);
        testEvent.setPayload(new HashMap<>());

        testRequest = new AgentEventRequest();
        testRequest.setEvent(testEvent);
    }

    @Test
    void eventAckProtocol_FirstSubmission_ReturnsAcceptedAck() throws Exception {
        // Act & Assert - First submission should be accepted
        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.seq").value(1))
                .andExpect(jsonPath("$.data.accepted").value(true))
                .andExpect(jsonPath("$.data.duplicate").value(false))
                .andExpect(jsonPath("$.data.errorCode").doesNotExist());
    }

    @Test
    void eventAckProtocol_DuplicateSubmission_ReturnsDuplicateAck() throws Exception {
        // Arrange - Submit event first time
        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk());

        // Act & Assert - Second submission should be marked as duplicate
        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.seq").value(1))
                .andExpect(jsonPath("$.data.accepted").value(true))
                .andExpect(jsonPath("$.data.duplicate").value(true))
                .andExpect(jsonPath("$.data.errorCode").doesNotExist());
    }

    @Test
    void eventAckProtocol_MultipleEvents_MaintainsSequenceNumbers() throws Exception {
        // Arrange - Create multiple events with different IDs and sequences
        TaskEvent event1 = createTestEvent("evt_seq_test_1", 1L);
        TaskEvent event2 = createTestEvent("evt_seq_test_2", 2L);
        TaskEvent event3 = createTestEvent("evt_seq_test_3", 3L);

        AgentEventRequest request1 = new AgentEventRequest();
        request1.setEvent(event1);
        AgentEventRequest request2 = new AgentEventRequest();
        request2.setEvent(event2);
        AgentEventRequest request3 = new AgentEventRequest();
        request3.setEvent(event3);

        // Act & Assert - Submit events in sequence
        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request1)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.seq").value(1))
                .andExpect(jsonPath("$.data.accepted").value(true))
                .andExpect(jsonPath("$.data.duplicate").value(false));

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request2)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.seq").value(2))
                .andExpect(jsonPath("$.data.accepted").value(true))
                .andExpect(jsonPath("$.data.duplicate").value(false));

        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request3)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.seq").value(3))
                .andExpect(jsonPath("$.data.accepted").value(true))
                .andExpect(jsonPath("$.data.duplicate").value(false));
    }

    @Test
    void eventDeduplication_RedisBasedStorage_WorksCorrectly() throws Exception {
        String eventId = "evt_dedup_test_" + System.currentTimeMillis();
        
        // Verify not duplicate initially
        assertFalse(deduplicationService.isDuplicate(eventId));
        
        // Mark as processed
        deduplicationService.markProcessed(eventId, 42L);
        
        // Verify now marked as duplicate
        assertTrue(deduplicationService.isDuplicate(eventId));
        
        // Verify sequence number retrieval
        Long originalSeq = deduplicationService.getOriginalSequence(eventId);
        assertEquals(42L, originalSeq);
    }

    @Test
    void eventAckProtocol_InvalidTaskId_ReturnsTaskNotFoundError() throws Exception {
        // Act & Assert
        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_nonexistent")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.seq").value(0))
                .andExpect(jsonPath("$.data.accepted").value(false))
                .andExpect(jsonPath("$.data.duplicate").value(false))
                .andExpect(jsonPath("$.data.errorCode").value("TASK_NOT_FOUND"));
    }

    @Test
    void eventAckProtocol_MissingEventId_ReturnsMissingEventIdError() throws Exception {
        // Arrange
        testEvent.setEventId(null);
        testRequest.setEvent(testEvent);

        // Act & Assert
        mockMvc.perform(post("/api/v1/events/ingest")
                        .param("taskId", "tsk_test123")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.seq").value(0))
                .andExpect(jsonPath("$.data.accepted").value(false))
                .andExpect(jsonPath("$.data.duplicate").value(false))
                .andExpect(jsonPath("$.data.errorCode").value("MISSING_EVENT_ID"));
    }

    @Test
    void eventHealthCheck_RedisConnectivity_ReturnsHealthy() throws Exception {
        // Act & Assert
        mockMvc.perform(get("/api/v1/events/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value("Event processing healthy"));
    }

    private TaskEvent createTestEvent(String eventId, long seq) {
        TaskEvent event = new TaskEvent();
        event.setEventId(eventId);
        event.setTaskId("tsk_test123");
        event.setType(EventType.TASK_STARTED);
        event.setTimestamp(Instant.now());
        event.setSeq(seq);
        event.setPayload(new HashMap<>());
        return event;
    }
}