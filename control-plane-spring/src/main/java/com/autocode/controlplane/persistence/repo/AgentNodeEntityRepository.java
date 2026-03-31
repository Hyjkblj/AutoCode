/**
 * JPA repository for registered agent nodes.
 */
package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.AgentNodeEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AgentNodeEntityRepository extends JpaRepository<AgentNodeEntity, String> {
}
