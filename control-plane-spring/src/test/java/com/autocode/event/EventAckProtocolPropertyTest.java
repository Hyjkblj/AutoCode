/**
 * Property-based tests for Event ACK Protocol compliance.
 * Validates Requirements 2.4 (Event ACK Protocol Compliance) and 2.5 (Event Deduplication).
 */
package com.autocode.event;

import com.autocode.protocol.model.EventAckResponse;
import net.jqwik.api.*;
import net.jqwik.api.constraints.AlphaChars;
import net.jqwik.api.constraints.LongRange;
import net.jqwik.api.constraints.StringLength;
import org.junit.jupiter.api.BeforeEach;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class EventAckProtocolPropertyTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private EventDeduplicationService deduplicationService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        deduplicationService = new EventDeduplicationService(redisTemplate);
    }

    /**
     * Property: For any valid event ID, isDuplicate should return false initially
     * **Validates: Requirements 2.5**
     */
    @Property
    void property_initial_duplicate_check_returns_false(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId) {
        
        // Arrange
        when(redisTemplate.hasKey("event:dedup:" + eventId)).thenReturn(false);

        // Act
        boolean result = deduplicationService.isDuplicate(eventId);

        // Assert
        assertFalse(result, "Initial duplicate check should return false for event: " + eventId);
        verify(redisTemplate).hasKey("event:dedup:" + eventId);
    }

    /**
     * Property: For any valid event ID and sequence, after marking as processed, 
     * isDuplicate should return true
     * **Validates: Requirements 2.5**
     */
    @Property
    void property_after_marking_processed_duplicate_check_returns_true(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 1, max = Long.MAX_VALUE) long sequence) {
        
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(redisTemplate.hasKey("event:dedup:" + eventId)).thenReturn(true);

        // Act
        deduplicationService.markProcessed(eventId, sequence);
        boolean result = deduplicationService.isDuplicate(eventId);

        // Assert
        assertTrue(result, "After marking as processed, duplicate check should return true for event: " + eventId);
        verify(valueOperations).set("event:dedup:" + eventId, "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:" + eventId, String.valueOf(sequence), Duration.ofHours(24));
    }

    /**
     * Property: For any valid event ID and sequence, after marking as processed,
     * getOriginalSequence should return the same sequence
     * **Validates: Requirements 2.4**
     */
    @Property
    void property_original_sequence_preservation(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 1, max = Long.MAX_VALUE) long sequence) {
        
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:" + eventId)).thenReturn(String.valueOf(sequence));

        // Act
        deduplicationService.markProcessed(eventId, sequence);
        Long retrievedSequence = deduplicationService.getOriginalSequence(eventId);

        // Assert
        assertEquals(sequence, retrievedSequence, 
            "Retrieved sequence should match original for event: " + eventId);
        verify(valueOperations).get("event:seq:" + eventId);
    }

    /**
     * Property: For any null or blank event ID, operations should handle gracefully
     * **Validates: Requirements 2.4, 2.5**
     */
    @Property
    void property_null_blank_event_id_handling(
            @ForAll("nullOrBlankStrings") String eventId,
            @ForAll @LongRange(min = 1, max = Long.MAX_VALUE) long sequence) {
        
        // Act & Assert
        assertFalse(deduplicationService.isDuplicate(eventId), 
            "isDuplicate should return false for null/blank event ID");
        
        assertNull(deduplicationService.getOriginalSequence(eventId), 
            "getOriginalSequence should return null for null/blank event ID");
        
        // Should not throw exception
        assertDoesNotThrow(() -> deduplicationService.markProcessed(eventId, sequence),
            "markProcessed should not throw for null/blank event ID");
        
        // Should not interact with Redis for null/blank IDs
        verify(redisTemplate, never()).hasKey(any());
        verify(redisTemplate, never()).opsForValue();
    }

    /**
     * Property: EventAckResponse should maintain consistency in its fields
     * **Validates: Requirements 2.4**
     */
    @Property
    void property_ack_response_consistency(
            @ForAll @LongRange(min = 0, max = Long.MAX_VALUE) long sequence,
            @ForAll boolean accepted,
            @ForAll boolean duplicate,
            @ForAll("errorCodes") String errorCode) {
        
        // Act
        EventAckResponse response = new EventAckResponse(sequence, accepted, duplicate, errorCode);

        // Assert
        assertEquals(sequence, response.getSequenceNumber(), "Sequence number should be preserved");
        assertEquals(accepted, response.isAccepted(), "Accepted status should be preserved");
        assertEquals(duplicate, response.isDuplicate(), "Duplicate status should be preserved");
        assertEquals(errorCode, response.getErrorCode(), "Error code should be preserved");
        
        // String representation should contain key information
        String toString = response.toString();
        assertTrue(toString.contains("seq=" + sequence), "toString should contain sequence");
        assertTrue(toString.contains("accepted=" + accepted), "toString should contain accepted status");
        assertTrue(toString.contains("duplicate=" + duplicate), "toString should contain duplicate status");
    }

    @Provide
    Arbitrary<String> nullOrBlankStrings() {
        return Arbitraries.oneOf(
            Arbitraries.just((String) null),
            Arbitraries.just(""),
            Arbitraries.just("   "),
            Arbitraries.just("\t\n")
        );
    }

    @Provide
    Arbitrary<String> errorCodes() {
        return Arbitraries.oneOf(
            Arbitraries.just((String) null),
            Arbitraries.just("MISSING_EVENT_ID"),
            Arbitraries.just("NODE_NOT_REGISTERED"),
            Arbitraries.just("INVALID_NODE_ID"),
            Arbitraries.just("TASK_NOT_FOUND"),
            Arbitraries.just("PROCESSING_ERROR")
        );
    }
}