package com.autocode.event;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository for Event entities.
 * Provides data access for event persistence and retrieval.
 */
@Repository
public interface EventRepository extends JpaRepository<EventEntity, String> {
    
    /**
     * Find all events for a specific task, ordered by sequence number.
     */
    List<EventEntity> findByTaskIdOrderBySeqNumAsc(String taskId);
    
    /**
     * Find the latest event for a task.
     */
    Optional<EventEntity> findFirstByTaskIdOrderBySeqNumDesc(String taskId);
    
    /**
     * Get the maximum sequence number for a task.
     */
    @Query("SELECT MAX(e.seqNum) FROM EventEntity e WHERE e.taskId = :taskId")
    Optional<Long> findMaxSeqNumByTaskId(@Param("taskId") String taskId);
    
    /**
     * Count events for a specific task.
     */
    long countByTaskId(String taskId);
    
    /**
     * Check if an event exists by event ID.
     */
    boolean existsByEventId(String eventId);
}
