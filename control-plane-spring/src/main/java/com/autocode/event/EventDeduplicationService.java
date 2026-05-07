/**
 * Redis-based event deduplication service.
 * Implements Requirements 2.5 (Event Deduplication).
 */
package com.autocode.event;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;

@Service
public class EventDeduplicationService {
    private static final Logger log = LoggerFactory.getLogger(EventDeduplicationService.class);
    
    // Redis key prefixes
    private static final String DEDUP_KEY_PREFIX = "event:dedup:";
    private static final String SEQ_KEY_PREFIX = "event:seq:";
    
    // TTL for deduplication entries (24 hours)
    private static final Duration DEDUP_TTL = Duration.ofHours(24);
    
    private final StringRedisTemplate redisTemplate;

    @Autowired
    public EventDeduplicationService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * Check if an event ID has already been processed.
     * 
     * @param eventId the event ID to check
     * @return true if the event is a duplicate, false otherwise
     */
    public boolean isDuplicate(String eventId) {
        if (eventId == null || eventId.isBlank()) {
            return false;
        }
        
        try {
            String dedupKey = DEDUP_KEY_PREFIX + eventId;
            Boolean exists = redisTemplate.hasKey(dedupKey);
            return Boolean.TRUE.equals(exists);
        } catch (Exception e) {
            log.error("Error checking duplicate for event {}: {}", eventId, e.getMessage());
            // In case of Redis failure, assume not duplicate to avoid blocking processing
            return false;
        }
    }

    /**
     * Mark an event as processed and store its sequence number.
     * 
     * @param eventId the event ID to mark as processed
     * @param sequenceNumber the sequence number of the event
     */
    public void markProcessed(String eventId, long sequenceNumber) {
        if (eventId == null || eventId.isBlank()) {
            return;
        }
        
        try {
            String dedupKey = DEDUP_KEY_PREFIX + eventId;
            String seqKey = SEQ_KEY_PREFIX + eventId;
            
            // Mark as processed with TTL
            redisTemplate.opsForValue().set(dedupKey, "processed", DEDUP_TTL);
            
            // Store sequence number with TTL for duplicate ACK responses
            redisTemplate.opsForValue().set(seqKey, String.valueOf(sequenceNumber), DEDUP_TTL);
            
            log.debug("Marked event {} as processed with sequence {}", eventId, sequenceNumber);
        } catch (Exception e) {
            log.error("Error marking event {} as processed: {}", eventId, e.getMessage());
            // Don't throw exception to avoid blocking the main processing flow
        }
    }

    /**
     * Get the original sequence number for a duplicate event.
     * 
     * @param eventId the event ID
     * @return the original sequence number, or null if not found
     */
    public Long getOriginalSequence(String eventId) {
        if (eventId == null || eventId.isBlank()) {
            return null;
        }
        
        try {
            String seqKey = SEQ_KEY_PREFIX + eventId;
            String seqStr = redisTemplate.opsForValue().get(seqKey);
            
            if (seqStr != null && !seqStr.isBlank()) {
                return Long.parseLong(seqStr);
            }
        } catch (Exception e) {
            log.error("Error retrieving original sequence for event {}: {}", eventId, e.getMessage());
        }
        
        return null;
    }

    /**
     * Clean up old deduplication entries (for maintenance purposes).
     * This method can be called periodically to clean up expired entries,
     * though Redis TTL should handle this automatically.
     * 
     * @param eventId the event ID to clean up
     */
    public void cleanup(String eventId) {
        if (eventId == null || eventId.isBlank()) {
            return;
        }
        
        try {
            String dedupKey = DEDUP_KEY_PREFIX + eventId;
            String seqKey = SEQ_KEY_PREFIX + eventId;
            
            redisTemplate.delete(dedupKey);
            redisTemplate.delete(seqKey);
            
            log.debug("Cleaned up deduplication entries for event {}", eventId);
        } catch (Exception e) {
            log.error("Error cleaning up event {}: {}", eventId, e.getMessage());
        }
    }

    /**
     * Get statistics about the deduplication service.
     * 
     * @return a string with basic statistics
     */
    public String getStats() {
        try {
            // Count keys with our prefixes (this is expensive, use sparingly)
            Long dedupCount = redisTemplate.countExistingKeys(
                redisTemplate.keys(DEDUP_KEY_PREFIX + "*")
            );
            Long seqCount = redisTemplate.countExistingKeys(
                redisTemplate.keys(SEQ_KEY_PREFIX + "*")
            );
            
            return String.format("Deduplication entries: %d, Sequence entries: %d", 
                dedupCount != null ? dedupCount : 0, 
                seqCount != null ? seqCount : 0);
        } catch (Exception e) {
            log.error("Error getting deduplication stats: {}", e.getMessage());
            return "Stats unavailable: " + e.getMessage();
        }
    }
}