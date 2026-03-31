/**
 * JPA repository for persisted task events.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.TaskEventEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface TaskEventEntityRepository extends JpaRepository<TaskEventEntity, String> {
    List<TaskEventEntity> findByTaskIdOrderBySeqNumAsc(String taskId);

    List<TaskEventEntity> findByTaskIdAndSeqNumGreaterThanOrderBySeqNumAsc(String taskId, long seqNum);

    List<TaskEventEntity> findTop200ByTaskIdAndSeqNumGreaterThanOrderBySeqNumAsc(String taskId, long seqNum);
}
