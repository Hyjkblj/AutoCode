/**
 * Comprehensive unit tests for Event handling services - deduplication and sequence handling.
 * Validates Requirement 6.4 (comprehensive test coverage for all core services).
 * 
 * This test complements EventDeduplicationServiceTest with integration-level scenarios.
 */
package com.autocode.event;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class EventServiceTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private EventDeduplicationService eventService;

    @BeforeEach
    void setUp() {
        eventService = new EventDeduplicationService(redisTemplate);
    }

    // ========== Sequence Handling Tests ==========

    @Test
    void sequenceHandling_FirstEvent_AssignsSequence() {
        // Arrange
        String eventId = "evt_first";
        long sequenceNumber = 1L;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        eventService.markProcessed(eventId, sequenceNumber);

        // Assert
        verify(valueOperations).set("event:dedup:evt_first", "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:evt_first", "1", Duration.ofHours(24));
    }

    @Test
    void sequenceHandling_MultipleEvents_MaintainsSequence() {
        // Arrange
        String[] eventIds = {"evt_1", "evt_2", "evt_3"};
        long[] sequences = {1L, 2L, 3L};
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        for (int i = 0; i < eventIds.length; i++) {
            eventService.markProcessed(eventIds[i], sequences[i]);
        }

        // Assert
        for (int i = 0; i < eventIds.length; i++) {
            verify(valueOperations).set("event:seq:" + eventIds[i], String.valueOf(sequences[i]), Duration.ofHours(24));
        }
    }

    @Test
    void sequenceHandling_DuplicateEvent_ReturnsOriginalSequence() {
        // Arrange
        String eventId = "evt_duplicate";
        long originalSequence = 42L;

        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_duplicate")).thenReturn("42");

        // Act
        Long retrievedSequence = eventService.getOriginalSequence(eventId);

        // Assert
        assertEquals(originalSequence, retrievedSequence);
        verify(valueOperations).get("event:seq:evt_duplicate");
    }

    @Test
    void sequenceHandling_LargeSequenceNumber_HandlesCorrectly() {
        // Arrange
        String eventId = "evt_large";
        long largeSequence = Long.MAX_VALUE - 1;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        eventService.markProcessed(eventId, largeSequence);

        // Assert
        verify(valueOperations).set("event:seq:evt_large", String.valueOf(largeSequence), Duration.ofHours(24));
    }

    @Test
    void sequenceHandling_ZeroSequence_HandlesCorrectly() {
        // Arrange
        String eventId = "evt_zero";
        long zeroSequence = 0L;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        eventService.markProcessed(eventId, zeroSequence);

        // Assert
        verify(valueOperations).set("event:seq:evt_zero", "0", Duration.ofHours(24));
    }

    // ========== Deduplication Workflow Tests ==========

    @Test
    void deduplicationWorkflow_NewEvent_ProcessesSuccessfully() {
        // Arrange
        String eventId = "evt_new";
        long sequence = 10L;

        when(redisTemplate.hasKey("event:dedup:evt_new")).thenReturn(false);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        boolean isDuplicate = eventService.isDuplicate(eventId);
        eventService.markProcessed(eventId, sequence);

        // Assert
        assertFalse(isDuplicate);
        verify(valueOperations).set("event:dedup:evt_new", "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:evt_new", "10", Duration.ofHours(24));
    }

    @Test
    void deduplicationWorkflow_DuplicateEvent_RejectsAndReturnsOriginalSequence() {
        // Arrange
        String eventId = "evt_dup";
        long originalSequence = 5L;

        when(redisTemplate.hasKey("event:dedup:evt_dup")).thenReturn(true);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_dup")).thenReturn("5");

        // Act
        boolean isDuplicate = eventService.isDuplicate(eventId);
        Long retrievedSequence = eventService.getOriginalSequence(eventId);

        // Assert
        assertTrue(isDuplicate);
        assertEquals(originalSequence, retrievedSequence);
        verify(valueOperations, never()).set(eq("event:dedup:evt_dup"), any(), any(Duration.class));
    }

    @Test
    void deduplicationWorkflow_ConcurrentDuplicates_HandlesGracefully() {
        // Arrange
        String eventId = "evt_concurrent";
        long sequence1 = 100L;

        // Simulate: first check says not duplicate, but by the time we mark it, it's already there
        when(redisTemplate.hasKey("event:dedup:evt_concurrent"))
                .thenReturn(false)
                .thenReturn(true);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        boolean isDuplicate1 = eventService.isDuplicate(eventId);
        eventService.markProcessed(eventId, sequence1);
        boolean isDuplicate2 = eventService.isDuplicate(eventId);

        // Assert
        assertFalse(isDuplicate1);
        assertTrue(isDuplicate2);
        verify(valueOperations).set("event:dedup:evt_concurrent", "processed", Duration.ofHours(24));
    }

    // ========== TTL and Expiration Tests ==========

    @Test
    void ttl_AllEntries_Use24HourExpiration() {
        // Arrange
        String eventId = "evt_ttl";
        long sequence = 1L;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        eventService.markProcessed(eventId, sequence);

        // Assert
        verify(valueOperations).set("event:dedup:evt_ttl", "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:evt_ttl", "1", Duration.ofHours(24));
    }

    @Test
    void cleanup_RemovesBothKeys() {
        // Arrange
        String eventId = "evt_cleanup";

        // Act
        eventService.cleanup(eventId);

        // Assert
        verify(redisTemplate).delete("event:dedup:evt_cleanup");
        verify(redisTemplate).delete("event:seq:evt_cleanup");
    }

    @Test
    void cleanup_MultipleEvents_RemovesAllKeys() {
        // Arrange
        String[] eventIds = {"evt_1", "evt_2", "evt_3"};

        // Act
        for (String eventId : eventIds) {
            eventService.cleanup(eventId);
        }

        // Assert
        for (String eventId : eventIds) {
            verify(redisTemplate).delete("event:dedup:" + eventId);
            verify(redisTemplate).delete("event:seq:" + eventId);
        }
    }

    // ========== Error Handling and Resilience Tests ==========

    @Test
    void errorHandling_RedisDownDuringCheck_ReturnsFalseToAllowProcessing() {
        // Arrange
        String eventId = "evt_redis_down";
        when(redisTemplate.hasKey("event:dedup:evt_redis_down"))
                .thenThrow(new RuntimeException("Redis connection failed"));

        // Act
        boolean isDuplicate = eventService.isDuplicate(eventId);

        // Assert
        assertFalse(isDuplicate); // Fail open to avoid blocking processing
    }

    @Test
    void errorHandling_RedisDownDuringMark_DoesNotThrow() {
        // Arrange
        String eventId = "evt_mark_fail";
        long sequence = 1L;

        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        doThrow(new RuntimeException("Redis write failed"))
                .when(valueOperations).set(eq("event:dedup:evt_mark_fail"), any(), any(Duration.class));

        // Act & Assert
        assertDoesNotThrow(() -> eventService.markProcessed(eventId, sequence));
    }

    @Test
    void errorHandling_RedisDownDuringSequenceRetrieval_ReturnsNull() {
        // Arrange
        String eventId = "evt_seq_fail";
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_seq_fail"))
                .thenThrow(new RuntimeException("Redis read failed"));

        // Act
        Long sequence = eventService.getOriginalSequence(eventId);

        // Assert
        assertNull(sequence);
    }

    @Test
    void errorHandling_PartialRedisFailure_ContinuesProcessing() {
        // Arrange
        String eventId = "evt_partial_fail";
        long sequence = 1L;

        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        // Dedup key succeeds, sequence key fails
        doNothing().when(valueOperations).set("event:dedup:evt_partial_fail", "processed", Duration.ofHours(24));
        doThrow(new RuntimeException("Sequence write failed"))
                .when(valueOperations).set("event:seq:evt_partial_fail", "1", Duration.ofHours(24));

        // Act & Assert
        assertDoesNotThrow(() -> eventService.markProcessed(eventId, sequence));
        verify(valueOperations).set("event:dedup:evt_partial_fail", "processed", Duration.ofHours(24));
    }

    // ========== Statistics and Monitoring Tests ==========

    @Test
    void stats_WithEntries_ReturnsCorrectCounts() {
        // Arrange
        Set<String> dedupKeys = Set.of("event:dedup:evt_1", "event:dedup:evt_2", "event:dedup:evt_3");
        Set<String> seqKeys = Set.of("event:seq:evt_1", "event:seq:evt_2");

        when(redisTemplate.keys("event:dedup:*")).thenReturn(dedupKeys);
        when(redisTemplate.keys("event:seq:*")).thenReturn(seqKeys);
        when(redisTemplate.countExistingKeys(dedupKeys)).thenReturn(3L);
        when(redisTemplate.countExistingKeys(seqKeys)).thenReturn(2L);

        // Act
        String stats = eventService.getStats();

        // Assert
        assertEquals("Deduplication entries: 3, Sequence entries: 2", stats);
    }

    @Test
    void stats_EmptyRedis_ReturnsZeroCounts() {
        // Arrange
        Set<String> emptySet = Set.of();

        when(redisTemplate.keys("event:dedup:*")).thenReturn(emptySet);
        when(redisTemplate.keys("event:seq:*")).thenReturn(emptySet);
        when(redisTemplate.countExistingKeys(emptySet)).thenReturn(0L);

        // Act
        String stats = eventService.getStats();

        // Assert
        assertEquals("Deduplication entries: 0, Sequence entries: 0", stats);
    }

    @Test
    void stats_RedisFailure_ReturnsErrorMessage() {
        // Arrange
        when(redisTemplate.keys("event:dedup:*")).thenThrow(new RuntimeException("Redis error"));

        // Act
        String stats = eventService.getStats();

        // Assert
        assertTrue(stats.startsWith("Stats unavailable:"));
        assertTrue(stats.contains("Redis error"));
    }

    // ========== Edge Cases and Boundary Tests ==========

    @Test
    void edgeCase_VeryLongEventId_HandlesCorrectly() {
        // Arrange
        String longEventId = "evt_" + "x".repeat(1000);
        long sequence = 1L;

        when(redisTemplate.hasKey("event:dedup:" + longEventId)).thenReturn(false);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        boolean isDuplicate = eventService.isDuplicate(longEventId);
        eventService.markProcessed(longEventId, sequence);

        // Assert
        assertFalse(isDuplicate);
        verify(valueOperations).set("event:dedup:" + longEventId, "processed", Duration.ofHours(24));
    }

    @Test
    void edgeCase_SpecialCharactersInEventId_HandlesCorrectly() {
        // Arrange
        String specialEventId = "evt_!@#$%^&*()";
        long sequence = 1L;

        when(redisTemplate.hasKey("event:dedup:" + specialEventId)).thenReturn(false);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        boolean isDuplicate = eventService.isDuplicate(specialEventId);
        eventService.markProcessed(specialEventId, sequence);

        // Assert
        assertFalse(isDuplicate);
        verify(valueOperations).set("event:dedup:" + specialEventId, "processed", Duration.ofHours(24));
    }

    @Test
    void edgeCase_NegativeSequence_HandlesCorrectly() {
        // Arrange
        String eventId = "evt_negative";
        long negativeSequence = -1L;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        eventService.markProcessed(eventId, negativeSequence);

        // Assert
        verify(valueOperations).set("event:seq:evt_negative", "-1", Duration.ofHours(24));
    }

    @Test
    void edgeCase_SequenceOverflow_HandlesCorrectly() {
        // Arrange
        String eventId = "evt_overflow";
        long maxSequence = Long.MAX_VALUE;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        eventService.markProcessed(eventId, maxSequence);

        // Assert
        verify(valueOperations).set("event:seq:evt_overflow", String.valueOf(Long.MAX_VALUE), Duration.ofHours(24));
    }

    // ========== Integration Scenario Tests ==========

    @Test
    void integrationScenario_TypicalEventFlow_WorksEndToEnd() {
        // Arrange
        String eventId = "evt_integration";
        long sequence = 42L;

        when(redisTemplate.hasKey("event:dedup:evt_integration"))
                .thenReturn(false)
                .thenReturn(true);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_integration")).thenReturn("42");

        // Act & Assert - First processing
        assertFalse(eventService.isDuplicate(eventId));
        eventService.markProcessed(eventId, sequence);

        // Act & Assert - Duplicate attempt
        assertTrue(eventService.isDuplicate(eventId));
        Long retrievedSequence = eventService.getOriginalSequence(eventId);
        assertEquals(sequence, retrievedSequence);

        // Act & Assert - Cleanup
        eventService.cleanup(eventId);
        verify(redisTemplate).delete("event:dedup:evt_integration");
        verify(redisTemplate).delete("event:seq:evt_integration");
    }

    @Test
    void integrationScenario_HighThroughput_HandlesMultipleEvents() {
        // Arrange
        int eventCount = 100;
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // Act
        for (int i = 0; i < eventCount; i++) {
            String eventId = "evt_" + i;
            when(redisTemplate.hasKey("event:dedup:" + eventId)).thenReturn(false);
            
            assertFalse(eventService.isDuplicate(eventId));
            eventService.markProcessed(eventId, (long) i);
        }

        // Assert
        verify(valueOperations, times(eventCount)).set(startsWith("event:dedup:"), eq("processed"), eq(Duration.ofHours(24)));
        verify(valueOperations, times(eventCount)).set(startsWith("event:seq:"), anyString(), eq(Duration.ofHours(24)));
    }
}
