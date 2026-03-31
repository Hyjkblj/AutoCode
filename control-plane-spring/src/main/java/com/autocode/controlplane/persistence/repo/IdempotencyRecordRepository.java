/**
 * JPA repository for idempotency key mappings.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.IdempotencyRecordEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface IdempotencyRecordRepository extends JpaRepository<IdempotencyRecordEntity, String> {
}
