/**
 * JPA repository for persisted task events.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.TaskEventEntity;
import com.autocode.protocol.model.EventType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface TaskEventEntityRepository extends JpaRepository<TaskEventEntity, String> {
    List<TaskEventEntity> findByTaskIdOrderBySeqNumAsc(String taskId);

    List<TaskEventEntity> findByTaskIdAndSeqNumGreaterThanOrderBySeqNumAsc(String taskId, long seqNum);

    List<TaskEventEntity> findTop200ByTaskIdAndSeqNumGreaterThanOrderBySeqNumAsc(String taskId, long seqNum);

    Optional<TaskEventEntity> findTopByTaskIdOrderBySeqNumDesc(String taskId);

    Optional<TaskEventEntity> findTopByTaskIdAndEventTypeOrderBySeqNumDesc(String taskId, EventType eventType);
}
