/**
 * Simplified unit tests for EventDeduplicationService - Redis-based deduplication.
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

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class EventDeduplicationServiceSimpleTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private EventDeduplicationService deduplicationService;

    @BeforeEach
    void setUp() {
        deduplicationService = new EventDeduplicationService(redisTemplate);
    }

    @Test
    void isDuplicate_NotDuplicate_ReturnsFalse() {
        // Arrange
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenReturn(false);

        // Act
        boolean result = deduplicationService.isDuplicate("evt_123");

        // Assert
        assertFalse(result);
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void isDuplicate_IsDuplicate_ReturnsTrue() {
        // Arrange
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenReturn(true);

        // Act
        boolean result = deduplicationService.isDuplicate("evt_123");

        // Assert
        assertTrue(result);
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void markProcessed_ValidEventId_StoresInRedis() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        
        // Act
        deduplicationService.markProcessed("evt_123", 42L);

        // Assert
        verify(valueOperations).set("event:dedup:evt_123", "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:evt_123", "42", Duration.ofHours(24));
    }

    @Test
    void getOriginalSequence_ValidEventId_ReturnsSequence() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_123")).thenReturn("42");

        // Act
        Long result = deduplicationService.getOriginalSequence("evt_123");

        // Assert
        assertEquals(42L, result);
        verify(valueOperations).get("event:seq:evt_123");
    }

    @Test
    void isDuplicate_NullEventId_ReturnsFalse() {
        // Act
        boolean result = deduplicationService.isDuplicate(null);

        // Assert
        assertFalse(result);
        verify(redisTemplate, never()).hasKey(any());
    }

    @Test
    void markProcessed_NullEventId_DoesNothing() {
        // Act
        deduplicationService.markProcessed(null, 42L);

        // Assert
        verify(redisTemplate, never()).opsForValue();
    }

    @Test
    void getOriginalSequence_NullEventId_ReturnsNull() {
        // Act
        Long result = deduplicationService.getOriginalSequence(null);

        // Assert
        assertNull(result);
        verify(redisTemplate, never()).opsForValue();
    }
}