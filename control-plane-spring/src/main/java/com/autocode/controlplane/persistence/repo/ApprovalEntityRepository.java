/**
 * JPA repository for approvals.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.ApprovalEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ApprovalEntityRepository extends JpaRepository<ApprovalEntity, String> {
}
