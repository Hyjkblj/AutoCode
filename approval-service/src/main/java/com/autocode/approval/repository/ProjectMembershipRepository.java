package com.autocode.approval.repository;

import com.autocode.approval.entity.ProjectMembershipEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository for project membership entities.
 */
@Repository
public interface ProjectMembershipRepository extends JpaRepository<ProjectMembershipEntity, Long> {

    /**
     * Find all memberships for a specific project.
     */
    List<ProjectMembershipEntity> findByProjectId(String projectId);

    /**
     * Find all projects for a specific user.
     */
    List<ProjectMembershipEntity> findByUserId(String userId);

    /**
     * Find membership for a user in a specific project.
     */
    Optional<ProjectMembershipEntity> findByProjectIdAndUserId(String projectId, String userId);

    /**
     * Check if user is a member of a project.
     */
    boolean existsByProjectIdAndUserId(String projectId, String userId);

    /**
     * Delete membership.
     */
    void deleteByProjectIdAndUserId(String projectId, String userId);
}
