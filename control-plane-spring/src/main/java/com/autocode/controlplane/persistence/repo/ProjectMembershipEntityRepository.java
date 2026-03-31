package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.ProjectMembershipEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ProjectMembershipEntityRepository extends JpaRepository<ProjectMembershipEntity, ProjectMembershipEntity.Pk> {
    boolean existsByProjectIdAndUserId(String projectId, String userId);
}

