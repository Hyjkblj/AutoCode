/**
 * Comprehensive property-based tests for Event Deduplication functionality.
 * 
 * Task 4.4: Write property tests for event deduplication
 * Property 7: Event Deduplication
 * Validates: Requirements 2.5
 * 
 * These tests validate that "For any duplicate event submission (same eventId), 
 * the Control Plane SHALL detect the duplicate, return an ACK response with 
 * duplicate=true, and preserve the original sequence number."
 */
package com.autocode.event;

import net.jqwik.api.*;
import net.jqwik.api.constraints.AlphaChars;
import net.jqwik.api.constraints.LongRange;
import net.jqwik.api.constraints.StringLength;
import net.jqwik.time.api.DateTimes;
import org.junit.jupiter.api.BeforeEach;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;
import java.util.HashSet;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class EventDeduplicationPropertyTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private EventDeduplicationService deduplicationService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        deduplicationService = new EventDeduplicationService(redisTemplate);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
    }

    /**
     * Property: For any valid event ID, initial duplicate check should return false
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 100)
    @Label("Initial duplicate check returns false for any valid event ID")
    void property_7_initial_duplicate_check_returns_false(
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
     * duplicate check should return true
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 100)
    @Label("After marking as processed, duplicate check returns true")
    void property_7_after_marking_processed_duplicate_check_returns_true(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 0, max = Long.MAX_VALUE) long sequence) {
        
        // Arrange
        when(redisTemplate.hasKey("event:dedup:" + eventId)).thenReturn(true);

        // Act
        deduplicationService.markProcessed(eventId, sequence);
        boolean result = deduplicationService.isDuplicate(eventId);

        // Assert
        assertTrue(result, "After marking as processed, duplicate check should return true for event: " + eventId);
        verify(valueOperations).set("event:dedup:" + eventId, "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:" + eventId, String.valueOf(sequence), Duration.ofHours(24));
        verify(redisTemplate).hasKey("event:dedup:" + eventId);
    }

    /**
     * Property: For any valid event ID and sequence, after marking as processed,
     * getOriginalSequence should return the same sequence
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 100)
    @Label("Original sequence number is preserved for duplicates")
    void property_7_original_sequence_preservation(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 0, max = Long.MAX_VALUE) long sequence) {
        
        // Arrange
        when(valueOperations.get("event:seq:" + eventId)).thenReturn(String.valueOf(sequence));

        // Act
        deduplicationService.markProcessed(eventId, sequence);
        Long retrievedSequence = deduplicationService.getOriginalSequence(eventId);

        // Assert
        assertEquals(sequence, retrievedSequence, 
            "Retrieved sequence should match original for event: " + eventId);
        verify(valueOperations).set("event:seq:" + eventId, String.valueOf(sequence), Duration.ofHours(24));
        verify(valueOperations).get("event:seq:" + eventId);
    }

    /**
     * Property: For any list of events with the same event ID, only the first should be 
     * considered non-duplicate, all subsequent should be duplicates with preserved sequence
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 50)
    @Label("Multiple submissions with same event ID are handled correctly")
    void property_7_multiple_duplicate_submissions(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 1, max = 10000) long originalSequence) {
        
        // Mock Redis behavior for multiple submissions
        when(redisTemplate.hasKey("event:dedup:" + eventId))
            .thenReturn(false)  // First call - not duplicate
            .thenReturn(true);  // Subsequent calls - duplicate
        
        when(valueOperations.get("event:seq:" + eventId))
            .thenReturn(String.valueOf(originalSequence));

        // Act - First submission
        boolean firstIsDuplicate = deduplicationService.isDuplicate(eventId);
        deduplicationService.markProcessed(eventId, originalSequence);
        
        // Act - Second submission
        boolean secondIsDuplicate = deduplicationService.isDuplicate(eventId);
        Long retrievedSequence = deduplicationService.getOriginalSequence(eventId);
        
        // Assert first submission
        assertFalse(firstIsDuplicate, "First submission should not be duplicate");
        
        // Assert second submission
        assertTrue(secondIsDuplicate, "Second submission should be detected as duplicate");
        assertEquals(originalSequence, retrievedSequence, 
            "Second submission should preserve original sequence number");
        
        // Verify Redis interactions
        verify(valueOperations).set("event:dedup:" + eventId, "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:" + eventId, String.valueOf(originalSequence), Duration.ofHours(24));
    }

    /**
     * Property: For any set of different event IDs, each should be treated independently
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 50)
    @Label("Different event IDs are handled independently")
    void property_7_different_event_ids_independent_handling(
            @ForAll @AlphaChars @StringLength(min = 1, max = 32) String eventId1,
            @ForAll @AlphaChars @StringLength(min = 1, max = 32) String eventId2,
            @ForAll @LongRange(min = 0, max = 1000) long baseSequence) {
        
        // Ensure different event IDs
        if (eventId1.equals(eventId2)) {
            eventId2 = eventId2 + "_different";
        }
        
        // Mock Redis to return false for all hasKey calls (no duplicates initially)
        when(redisTemplate.hasKey(anyString())).thenReturn(false);
        
        // Act - Mark both events as processed with different sequences
        long sequence1 = baseSequence;
        long sequence2 = baseSequence + 1;
        
        boolean isDuplicate1 = deduplicationService.isDuplicate(eventId1);
        deduplicationService.markProcessed(eventId1, sequence1);
        
        boolean isDuplicate2 = deduplicationService.isDuplicate(eventId2);
        deduplicationService.markProcessed(eventId2, sequence2);
        
        // Assert
        assertFalse(isDuplicate1, "Event " + eventId1 + " should not be duplicate initially");
        assertFalse(isDuplicate2, "Event " + eventId2 + " should not be duplicate initially");
        
        // Verify Redis interactions for both events
        verify(redisTemplate).hasKey("event:dedup:" + eventId1);
        verify(redisTemplate).hasKey("event:dedup:" + eventId2);
        verify(valueOperations).set("event:dedup:" + eventId1, "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:" + eventId1, String.valueOf(sequence1), Duration.ofHours(24));
        verify(valueOperations).set("event:dedup:" + eventId2, "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:" + eventId2, String.valueOf(sequence2), Duration.ofHours(24));
    }

    /**
     * Property: For any null or blank event ID, operations should handle gracefully
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 50)
    @Label("Null and blank event IDs are handled gracefully")
    void property_7_null_blank_event_id_handling(
            @ForAll("nullOrBlankStrings") String eventId,
            @ForAll @LongRange(min = 0, max = Long.MAX_VALUE) long sequence) {
        
        // Act & Assert
        assertFalse(deduplicationService.isDuplicate(eventId), 
            "isDuplicate should return false for null/blank event ID: '" + eventId + "'");
        
        assertNull(deduplicationService.getOriginalSequence(eventId), 
            "getOriginalSequence should return null for null/blank event ID: '" + eventId + "'");
        
        // Should not throw exception
        assertDoesNotThrow(() -> deduplicationService.markProcessed(eventId, sequence),
            "markProcessed should not throw for null/blank event ID: '" + eventId + "'");
        
        // Should not interact with Redis for null/blank IDs
        verify(redisTemplate, never()).hasKey(any());
        verify(redisTemplate, never()).opsForValue();
    }

    /**
     * Property: For any event ID, cleanup operation should handle gracefully
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 50)
    @Label("Cleanup operations handle all event IDs gracefully")
    void property_7_cleanup_operations_graceful_handling(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId) {
        
        // Act - Should not throw exception
        assertDoesNotThrow(() -> deduplicationService.cleanup(eventId),
            "Cleanup should not throw for event ID: " + eventId);
        
        // Assert - Verify Redis delete operations were called
        verify(redisTemplate).delete("event:dedup:" + eventId);
        verify(redisTemplate).delete("event:seq:" + eventId);
    }

    /**
     * Property: For any event ID, TTL behavior should be consistent
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 50)
    @Label("TTL behavior is consistent for all event IDs")
    void property_7_ttl_behavior_consistency(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 0, max = Long.MAX_VALUE) long sequence) {
        
        // Act
        deduplicationService.markProcessed(eventId, sequence);
        
        // Assert - Verify TTL is set correctly for both keys
        verify(valueOperations).set("event:dedup:" + eventId, "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:" + eventId, String.valueOf(sequence), Duration.ofHours(24));
        
        // Verify TTL duration is exactly 24 hours
        Duration expectedTTL = Duration.ofHours(24);
        verify(valueOperations).set(eq("event:dedup:" + eventId), eq("processed"), eq(expectedTTL));
        verify(valueOperations).set(eq("event:seq:" + eventId), eq(String.valueOf(sequence)), eq(expectedTTL));
    }

    /**
     * Property: For any event ID with Redis errors, service should degrade gracefully
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 30)
    @Label("Service degrades gracefully under Redis errors")
    void property_7_redis_error_graceful_degradation(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId,
            @ForAll @LongRange(min = 0, max = Long.MAX_VALUE) long sequenceNumber) {
        
        // Arrange - Mock Redis to throw exceptions
        when(redisTemplate.hasKey(anyString())).thenThrow(new RuntimeException("Redis connection error"));
        when(valueOperations.get(anyString())).thenThrow(new RuntimeException("Redis read error"));
        doThrow(new RuntimeException("Redis write error")).when(valueOperations).set(anyString(), anyString(), any(Duration.class));
        
        // Act & Assert - Should not throw exceptions, should degrade gracefully
        assertDoesNotThrow(() -> {
            boolean isDuplicate = deduplicationService.isDuplicate(eventId);
            // In case of Redis failure, should assume not duplicate to avoid blocking processing
            assertFalse(isDuplicate, "Should return false on Redis error to avoid blocking processing");
        }, "isDuplicate should handle Redis errors gracefully");
        
        assertDoesNotThrow(() -> {
            Long retrievedSequence = deduplicationService.getOriginalSequence(eventId);
            assertNull(retrievedSequence, "Should return null on Redis error");
        }, "getOriginalSequence should handle Redis errors gracefully");
        
        assertDoesNotThrow(() -> deduplicationService.markProcessed(eventId, sequenceNumber),
            "markProcessed should handle Redis errors gracefully");
    }

    /**
     * Property: For any event ID, statistics should be retrievable
     * **Validates: Requirements 2.5**
     */
    @Property(tries = 30)
    @Label("Statistics are retrievable for any state")
    void property_7_statistics_retrievable(
            @ForAll @AlphaChars @StringLength(min = 1, max = 64) String eventId) {
        
        // Arrange - Mock Redis keys operations
        when(redisTemplate.keys("event:dedup:*")).thenReturn(Set.of("event:dedup:" + eventId));
        when(redisTemplate.keys("event:seq:*")).thenReturn(Set.of("event:seq:" + eventId));
        when(redisTemplate.countExistingKeys(any())).thenReturn(1L);
        
        // Act
        String stats = deduplicationService.getStats();
        
        // Assert
        assertNotNull(stats, "Statistics should not be null");
        assertTrue(stats.contains("Deduplication entries"), "Statistics should contain deduplication count");
        assertTrue(stats.contains("Sequence entries"), "Statistics should contain sequence count");
        
        // Verify Redis operations
        verify(redisTemplate).keys("event:dedup:*");
        verify(redisTemplate).keys("event:seq:*");
    }

    // Providers for custom data generation

    @Provide
    Arbitrary<String> nullOrBlankStrings() {
        return Arbitraries.oneOf(
            Arbitraries.just((String) null),
            Arbitraries.just(""),
            Arbitraries.just("   "),
            Arbitraries.just("\t\n\r"),
            Arbitraries.just("  \t  ")
        );
    }

    @Provide
    Arbitrary<List<Long>> sequenceList() {
        return Arbitraries.longs()
            .between(0L, 10000L)
            .list()
            .ofMinSize(2)
            .ofMaxSize(10);
    }

    @Provide
    Arbitrary<Set<String>> uniqueEventIds() {
        return Arbitraries.strings()
            .withCharRange('a', 'z')
            .ofMinLength(5)
            .ofMaxLength(20)
            .set()
            .ofMinSize(2)
            .ofMaxSize(10);
    }
}