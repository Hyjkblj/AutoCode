/**
 * Unit tests for EventDeduplicationService - Redis-based deduplication.
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
class EventDeduplicationServiceTest {

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
    void isDuplicate_NotDuplicate() {
        // Arrange
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenReturn(false);

        // Act
        boolean result = deduplicationService.isDuplicate("evt_123");

        // Assert
        assertFalse(result);
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void isDuplicate_IsDuplicate() {
        // Arrange
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenReturn(true);

        // Act
        boolean result = deduplicationService.isDuplicate("evt_123");

        // Assert
        assertTrue(result);
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void isDuplicate_NullEventId() {
        // Act
        boolean result = deduplicationService.isDuplicate(null);

        // Assert
        assertFalse(result);
        verify(redisTemplate, never()).hasKey(any());
    }

    @Test
    void isDuplicate_BlankEventId() {
        // Act
        boolean result = deduplicationService.isDuplicate("  ");

        // Assert
        assertFalse(result);
        verify(redisTemplate, never()).hasKey(any());
    }

    @Test
    void isDuplicate_RedisException() {
        // Arrange
        when(redisTemplate.hasKey("event:dedup:evt_123")).thenThrow(new RuntimeException("Redis error"));

        // Act
        boolean result = deduplicationService.isDuplicate("evt_123");

        // Assert
        assertFalse(result); // Should return false on Redis failure to avoid blocking
        verify(redisTemplate).hasKey("event:dedup:evt_123");
    }

    @Test
    void markProcessed_Success() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        
        // Act
        deduplicationService.markProcessed("evt_123", 42L);

        // Assert
        verify(valueOperations).set("event:dedup:evt_123", "processed", Duration.ofHours(24));
        verify(valueOperations).set("event:seq:evt_123", "42", Duration.ofHours(24));
    }

    @Test
    void markProcessed_NullEventId() {
        // Act
        deduplicationService.markProcessed(null, 42L);

        // Assert
        verify(valueOperations, never()).set(any(), any(), any(Duration.class));
    }

    @Test
    void markProcessed_BlankEventId() {
        // Act
        deduplicationService.markProcessed("  ", 42L);

        // Assert
        verify(valueOperations, never()).set(any(), any(), any(Duration.class));
    }

    @Test
    void markProcessed_RedisException() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        doThrow(new RuntimeException("Redis error")).when(valueOperations)
                .set(eq("event:dedup:evt_123"), eq("processed"), any(Duration.class));

        // Act & Assert - should not throw exception
        assertDoesNotThrow(() -> deduplicationService.markProcessed("evt_123", 42L));
    }

    @Test
    void getOriginalSequence_Success() {
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
    void getOriginalSequence_NotFound() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_123")).thenReturn(null);

        // Act
        Long result = deduplicationService.getOriginalSequence("evt_123");

        // Assert
        assertNull(result);
        verify(valueOperations).get("event:seq:evt_123");
    }

    @Test
    void getOriginalSequence_NullEventId() {
        // Act
        Long result = deduplicationService.getOriginalSequence(null);

        // Assert
        assertNull(result);
        verify(valueOperations, never()).get(any());
    }

    @Test
    void getOriginalSequence_BlankEventId() {
        // Act
        Long result = deduplicationService.getOriginalSequence("  ");

        // Assert
        assertNull(result);
        verify(valueOperations, never()).get(any());
    }

    @Test
    void getOriginalSequence_InvalidNumber() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_123")).thenReturn("not-a-number");

        // Act
        Long result = deduplicationService.getOriginalSequence("evt_123");

        // Assert
        assertNull(result);
    }

    @Test
    void getOriginalSequence_RedisException() {
        // Arrange
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("event:seq:evt_123")).thenThrow(new RuntimeException("Redis error"));

        // Act
        Long result = deduplicationService.getOriginalSequence("evt_123");

        // Assert
        assertNull(result);
    }

    @Test
    void cleanup_Success() {
        // Act
        deduplicationService.cleanup("evt_123");

        // Assert
        verify(redisTemplate).delete("event:dedup:evt_123");
        verify(redisTemplate).delete("event:seq:evt_123");
    }

    @Test
    void cleanup_NullEventId() {
        // Act
        deduplicationService.cleanup(null);

        // Assert
        verify(redisTemplate, never()).delete(anyString());
    }

    @Test
    void cleanup_BlankEventId() {
        // Act
        deduplicationService.cleanup("  ");

        // Assert
        verify(redisTemplate, never()).delete(anyString());
    }

    @Test
    void getStats_Success() {
        // Arrange
        Set<String> dedupKeys = Set.of("event:dedup:evt_1", "event:dedup:evt_2");
        Set<String> seqKeys = Set.of("event:seq:evt_1", "event:seq:evt_2", "event:seq:evt_3");
        
        when(redisTemplate.keys("event:dedup:*")).thenReturn(dedupKeys);
        when(redisTemplate.keys("event:seq:*")).thenReturn(seqKeys);
        when(redisTemplate.countExistingKeys(dedupKeys)).thenReturn(2L);
        when(redisTemplate.countExistingKeys(seqKeys)).thenReturn(3L);

        // Act
        String result = deduplicationService.getStats();

        // Assert
        assertEquals("Deduplication entries: 2, Sequence entries: 3", result);
    }

    @Test
    void getStats_RedisException() {
        // Arrange
        when(redisTemplate.keys("event:dedup:*")).thenThrow(new RuntimeException("Redis error"));

        // Act
        String result = deduplicationService.getStats();

        // Assert
        assertTrue(result.startsWith("Stats unavailable:"));
    }
}