/**
 * JPA repository for audit logs.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.AuditLogEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface AuditLogRepository extends JpaRepository<AuditLogEntity, String> {
    List<AuditLogEntity> findTop50ByTaskIdOrderByCreatedAtDesc(String taskId);

    @Query(value = """
            SELECT * FROM audit_logs
            WHERE task_id = :taskId
            ORDER BY created_at DESC, audit_id DESC
            LIMIT 1
            """, nativeQuery = true)
    AuditLogEntity findLatestForTask(@Param("taskId") String taskId);

    List<AuditLogEntity> findByTaskIdOrderByCreatedAtAscAuditIdAsc(String taskId);
}
