package com.autocode.event;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * Unit tests for EventDeduplicationService.
 * Validates Requirements 2.5 (Event Deduplication).
 */
@ExtendWith(MockitoExtension.class)
class EventDeduplicationServiceTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private EventDeduplicationService service;

    @BeforeEach
    void setUp() {
        lenient().when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        service = new EventDeduplicationService(redisTemplate, 24);
    }

    @Test
    void testIsDuplicate_NotDuplicate() {
        // Given
        String eventId = "evt_123";
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenReturn(false);

        // When
        boolean result = service.isDuplicate(eventId);

        // Then
        assertFalse(result);
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void testIsDuplicate_IsDuplicate() {
        // Given
        String eventId = "evt_123";
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenReturn(true);

        // When
        boolean result = service.isDuplicate(eventId);

        // Then
        assertTrue(result);
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void testIsDuplicate_NullEventId() {
        // When
        boolean result = service.isDuplicate(null);

        // Then
        assertFalse(result);
        verify(redisTemplate, never()).hasKey(anyString());
    }

    @Test
    void testIsDuplicate_BlankEventId() {
        // When
        boolean result = service.isDuplicate("  ");

        // Then
        assertFalse(result);
        verify(redisTemplate, never()).hasKey(anyString());
    }

    @Test
    void testMarkProcessed() {
        // Given
        String eventId = "evt_123";
        long sequenceNumber = 42L;

        // When
        service.markProcessed(eventId, sequenceNumber);

        // Then
        verify(valueOperations).set(eq("event:dedup:evt_123"), eq("processed"), any(Duration.class));
        verify(valueOperations).set(eq("event:seq:evt_123"), eq("42"), any(Duration.class));
    }

    @Test
    void testMarkProcessed_NullEventId() {
        // When
        service.markProcessed(null, 42L);

        // Then
        verify(valueOperations, never()).set(anyString(), anyString(), any(Duration.class));
    }

    @Test
    void testGetOriginalSequence() {
        // Given
        String eventId = "evt_123";
        when(valueOperations.get("event:seq:evt_123")).thenReturn("42");

        // When
        Long result = service.getOriginalSequence(eventId);

        // Then
        assertEquals(42L, result);
        verify(valueOperations).get("event:seq:evt_123");
    }

    @Test
    void testGetOriginalSequence_NotFound() {
        // Given
        String eventId = "evt_123";
        when(valueOperations.get("event:seq:evt_123")).thenReturn(null);

        // When
        Long result = service.getOriginalSequence(eventId);

        // Then
        assertNull(result);
        verify(valueOperations).get("event:seq:evt_123");
    }

    @Test
    void testGetOriginalSequence_NullEventId() {
        // When
        Long result = service.getOriginalSequence(null);

        // Then
        assertNull(result);
        verify(valueOperations, never()).get(anyString());
    }

    @Test
    void testCleanup() {
        // Given
        String eventId = "evt_123";

        // When
        service.cleanup(eventId);

        // Then
        verify(redisTemplate).delete("event:dedup:evt_123");
        verify(redisTemplate).delete("event:seq:evt_123");
    }

    @Test
    void testCleanup_NullEventId() {
        // When
        service.cleanup(null);

        // Then
        verify(redisTemplate, never()).delete(anyString());
    }

    @Test
    void testIsDuplicate_RedisException() {
        // Given
        String eventId = "evt_123";
        when(redisTemplate.hasKey(anyString())).thenThrow(new RuntimeException("Redis error"));

        // When
        boolean result = service.isDuplicate(eventId);

        // Then - should return false to avoid blocking processing
        assertFalse(result);
    }

    @Test
    void testMarkProcessed_RedisException() {
        // Given
        String eventId = "evt_123";
        doThrow(new RuntimeException("Redis error"))
            .when(valueOperations).set(anyString(), anyString(), any(Duration.class));

        // When/Then - should not throw exception
        assertDoesNotThrow(() -> service.markProcessed(eventId, 42L));
    }
}
