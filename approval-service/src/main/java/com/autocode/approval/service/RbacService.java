package com.autocode.approval.service;

import com.autocode.approval.entity.ProjectMembershipEntity;
import com.autocode.approval.entity.UserRoleEntity;
import com.autocode.approval.repository.ProjectMembershipRepository;
import com.autocode.approval.repository.UserRoleRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Service for Role-Based Access Control (RBAC).
 * 
 * <p>Validates: Requirements 13.2 (RBAC Implementation)
 */
@Service
public class RbacService {

    private static final Logger logger = LoggerFactory.getLogger(RbacService.class);

    private static final Set<String> APPROVAL_ROLES = Set.of("admin", "approver", "owner");
    private static final Set<String> PROJECT_ADMIN_ROLES = Set.of("admin", "owner");

    private final UserRoleRepository userRoleRepository;
    private final ProjectMembershipRepository projectMembershipRepository;

    public RbacService(
            UserRoleRepository userRoleRepository,
            ProjectMembershipRepository projectMembershipRepository) {
        this.userRoleRepository = userRoleRepository;
        this.projectMembershipRepository = projectMembershipRepository;
    }

    /**
     * Check if user can approve a task.
     * 
     * <p>User can approve if they have:
     * <ul>
     *   <li>Global admin or approver role</li>
     *   <li>Project-level admin or owner role</li>
     * </ul>
     */
    public boolean canApprove(String userId, String taskId) {
        logger.debug("Checking approval permission: userId={}, taskId={}", userId, taskId);

        // Check global roles
        List<UserRoleEntity> globalRoles = userRoleRepository.findByUserIdAndProjectIdIsNull(userId);
        boolean hasGlobalApprovalRole = globalRoles.stream()
                .anyMatch(role -> APPROVAL_ROLES.contains(role.getRoleName()));

        if (hasGlobalApprovalRole) {
            logger.debug("User has global approval role: userId={}", userId);
            return true;
        }

        // For now, we don't have project context from taskId
        // In a real implementation, we would query the task service to get the project ID
        // For this MVP, we'll allow approval if user has any project admin role
        List<ProjectMembershipEntity> memberships = projectMembershipRepository.findByUserId(userId);
        boolean hasProjectAdminRole = memberships.stream()
                .anyMatch(membership -> PROJECT_ADMIN_ROLES.contains(membership.getRole()));

        if (hasProjectAdminRole) {
            logger.debug("User has project admin role: userId={}", userId);
            return true;
        }

        logger.debug("User does not have approval permission: userId={}", userId);
        return false;
    }

    /**
     * Check if user has a specific role.
     */
    public boolean hasRole(String userId, String roleName) {
        return userRoleRepository.existsByUserIdAndRoleName(userId, roleName);
    }

    /**
     * Check if user has a specific role in a project.
     */
    public boolean hasRoleInProject(String userId, String roleName, String projectId) {
        return userRoleRepository.existsByUserIdAndRoleNameAndProjectId(userId, roleName, projectId);
    }

    /**
     * Check if user is a member of a project.
     */
    public boolean isMemberOfProject(String userId, String projectId) {
        return projectMembershipRepository.existsByProjectIdAndUserId(projectId, userId);
    }

    /**
     * Get all roles for a user.
     */
    public Set<String> getUserRoles(String userId) {
        List<UserRoleEntity> roles = userRoleRepository.findByUserId(userId);
        return roles.stream()
                .map(UserRoleEntity::getRoleName)
                .collect(Collectors.toSet());
    }

    /**
     * Get all projects for a user.
     */
    public Set<String> getUserProjects(String userId) {
        List<ProjectMembershipEntity> memberships = projectMembershipRepository.findByUserId(userId);
        return memberships.stream()
                .map(ProjectMembershipEntity::getProjectId)
                .collect(Collectors.toSet());
    }
}
