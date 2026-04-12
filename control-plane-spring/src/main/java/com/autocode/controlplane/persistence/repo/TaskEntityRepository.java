/**
 * JPA repository for task persistence.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.TaskEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.domain.Pageable;

import java.time.Instant;
import java.util.List;

public interface TaskEntityRepository extends JpaRepository<TaskEntity, String> {
    boolean existsByStatusAndSessionKey(com.autocode.protocol.model.TaskStatus status, String sessionKey);

    default boolean existsRunningBySessionKey(String sessionKey) {
        if (sessionKey == null || sessionKey.isBlank()) {
            return false;
        }
        return existsByStatusAndSessionKey(com.autocode.protocol.model.TaskStatus.RUNNING, sessionKey);
    }

    @Modifying
    @Query(value = """
            UPDATE tasks
            SET assigned_node_id = :nodeId,
                status = 'RUNNING',
                updated_at = :now,
                leased_at = :now,
                lease_expires_at = :leaseExpiresAt
            WHERE task_id = :taskId
              AND status = 'QUEUED'
            """, nativeQuery = true)
    int claimQueuedTask(
            @Param("taskId") String taskId,
            @Param("nodeId") String nodeId,
            @Param("now") Instant now,
            @Param("leaseExpiresAt") Instant leaseExpiresAt
    );

    @Query(value = """
            SELECT * FROM tasks
            WHERE status = 'RUNNING'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < :now
            ORDER BY updated_at ASC
            LIMIT :limit
            """, nativeQuery = true)
    List<TaskEntity> findExpiredRunningLeases(@Param("now") Instant now, @Param("limit") int limit);

    @Modifying
    @Query(value = """
            UPDATE tasks
            SET status = 'QUEUED',
                assigned_node_id = NULL,
                leased_at = NULL,
                lease_expires_at = NULL,
                updated_at = :now
            WHERE task_id = :taskId
              AND status = 'RUNNING'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < :now
            """, nativeQuery = true)
    int requeueIfLeaseExpired(@Param("taskId") String taskId, @Param("now") Instant now);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select t from TaskEntity t where t.taskId = :taskId")
    java.util.Optional<TaskEntity> findOptionalByIdForUpdate(@Param("taskId") String taskId);

    /**
     * Selects the next eligible queued task for the given agent profile, ensuring lane serialization
     * (no other RUNNING task with the same session_key).
     *
     * Note: this is a scheduler helper to avoid queue churn/re-enqueue loops.
     */
    @Query(value = """
            SELECT * FROM tasks t
            WHERE t.status = 'QUEUED'
              AND (:profile IS NULL OR :profile = '' OR t.agent_profile = :profile)
              AND (
                    t.session_key IS NULL
                 OR t.session_key = ''
                 OR NOT EXISTS (
                      SELECT 1 FROM tasks r
                      WHERE r.status = 'RUNNING'
                        AND r.session_key = t.session_key
                 )
              )
            ORDER BY t.created_at ASC, t.updated_at ASC
            LIMIT 1
            """, nativeQuery = true)
    TaskEntity findNextEligibleQueuedTask(@Param("profile") String profile);

    @Query(value = """
            SELECT * FROM tasks t
            WHERE t.status = 'QUEUED'
              AND (t.next_run_at IS NULL OR t.next_run_at <= :now)
              AND (:profile IS NULL OR :profile = '' OR t.agent_profile = :profile)
              AND (
                    t.session_key IS NULL
                 OR t.session_key = ''
                 OR NOT EXISTS (
                      SELECT 1 FROM tasks r
                      WHERE r.status = 'RUNNING'
                        AND r.session_key = t.session_key
                 )
              )
            ORDER BY t.created_at ASC, t.updated_at ASC
            LIMIT 1
            """, nativeQuery = true)
    TaskEntity findNextEligibleQueuedTaskAt(@Param("profile") String profile, @Param("now") Instant now);

    @Query("""
            select t
            from TaskEntity t
            where t.projectId = :projectId
              and (:assistant is null or :assistant = '' or t.assistant = :assistant)
            order by t.createdAt desc
            """)
    List<TaskEntity> findRecentByProjectAndAssistant(
            @Param("projectId") String projectId,
            @Param("assistant") String assistant,
            Pageable pageable
    );
}
