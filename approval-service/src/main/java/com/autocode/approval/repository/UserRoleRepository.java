package com.autocode.approval.repository;

import com.autocode.approval.entity.UserRoleEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Repository for user role entities.
 */
@Repository
public interface UserRoleRepository extends JpaRepository<UserRoleEntity, Long> {

    /**
     * Find all roles for a specific user.
     */
    List<UserRoleEntity> findByUserId(String userId);

    /**
     * Find all roles for a user in a specific project.
     */
    List<UserRoleEntity> findByUserIdAndProjectId(String userId, String projectId);

    /**
     * Find all global roles for a user (projectId is null).
     */
    List<UserRoleEntity> findByUserIdAndProjectIdIsNull(String userId);

    /**
     * Check if user has a specific role.
     */
    boolean existsByUserIdAndRoleName(String userId, String roleName);

    /**
     * Check if user has a specific role in a project.
     */
    boolean existsByUserIdAndRoleNameAndProjectId(String userId, String roleName, String projectId);
}
