package com.autocode.approval.repository;

import com.autocode.approval.entity.ApprovalEntity;
import com.autocode.protocol.model.ApprovalDecision;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Repository for approval entities.
 */
@Repository
public interface ApprovalRepository extends JpaRepository<ApprovalEntity, String> {

    /**
     * Find all approvals for a specific task.
     */
    List<ApprovalEntity> findByTaskIdOrderByCreatedAtDesc(String taskId);

    /**
     * Find approvals by decision status.
     */
    List<ApprovalEntity> findByDecisionOrderByCreatedAtDesc(ApprovalDecision decision);

    /**
     * Find pending approvals for a specific task.
     */
    List<ApprovalEntity> findByTaskIdAndDecision(String taskId, ApprovalDecision decision);
}
