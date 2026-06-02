package com.autocode.approval.service;

import com.autocode.approval.entity.ProjectMembershipEntity;
import com.autocode.approval.entity.UserRoleEntity;
import com.autocode.approval.repository.ProjectMembershipRepository;
import com.autocode.approval.repository.UserRoleRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RbacServiceTest {

    @Mock
    private UserRoleRepository userRoleRepository;

    @Mock
    private ProjectMembershipRepository projectMembershipRepository;

    private RbacService rbacService;

    @BeforeEach
    void setUp() {
        rbacService = new RbacService(userRoleRepository, projectMembershipRepository);
    }

    @Test
    void canApprove_GlobalAdminRole() {
        // Given
        String userId = "user_001";
        String taskId = "task_001";

        UserRoleEntity adminRole = new UserRoleEntity();
        adminRole.setUserId(userId);
        adminRole.setRoleName("admin");
        adminRole.setProjectId(null); // Global role

        when(userRoleRepository.findByUserIdAndProjectIdIsNull(userId))
                .thenReturn(Arrays.asList(adminRole));

        // When
        boolean result = rbacService.canApprove(userId, taskId);

        // Then
        assertTrue(result);
        verify(userRoleRepository).findByUserIdAndProjectIdIsNull(userId);
        verify(projectMembershipRepository, never()).findByUserId(userId);
    }

    @Test
    void canApprove_GlobalApproverRole() {
        // Given
        String userId = "user_001";
        String taskId = "task_001";

        UserRoleEntity approverRole = new UserRoleEntity();
        approverRole.setUserId(userId);
        approverRole.setRoleName("approver");
        approverRole.setProjectId(null); // Global role

        when(userRoleRepository.findByUserIdAndProjectIdIsNull(userId))
                .thenReturn(Arrays.asList(approverRole));

        // When
        boolean result = rbacService.canApprove(userId, taskId);

        // Then
        assertTrue(result);
        verify(userRoleRepository).findByUserIdAndProjectIdIsNull(userId);
    }

    @Test
    void canApprove_ProjectOwnerRole() {
        // Given
        String userId = "user_001";
        String taskId = "task_001";

        when(userRoleRepository.findByUserIdAndProjectIdIsNull(userId))
                .thenReturn(Collections.emptyList()); // No global roles

        ProjectMembershipEntity membership = new ProjectMembershipEntity();
        membership.setUserId(userId);
        membership.setProjectId("project_001");
        membership.setRole("owner");

        when(projectMembershipRepository.findByUserId(userId))
                .thenReturn(Arrays.asList(membership));

        // When
        boolean result = rbacService.canApprove(userId, taskId);

        // Then
        assertTrue(result);
        verify(userRoleRepository).findByUserIdAndProjectIdIsNull(userId);
        verify(projectMembershipRepository).findByUserId(userId);
    }

    @Test
    void canApprove_ProjectAdminRole() {
        // Given
        String userId = "user_001";
        String taskId = "task_001";

        when(userRoleRepository.findByUserIdAndProjectIdIsNull(userId))
                .thenReturn(Collections.emptyList()); // No global roles

        ProjectMembershipEntity membership = new ProjectMembershipEntity();
        membership.setUserId(userId);
        membership.setProjectId("project_001");
        membership.setRole("admin");

        when(projectMembershipRepository.findByUserId(userId))
                .thenReturn(Arrays.asList(membership));

        // When
        boolean result = rbacService.canApprove(userId, taskId);

        // Then
        assertTrue(result);
        verify(userRoleRepository).findByUserIdAndProjectIdIsNull(userId);
        verify(projectMembershipRepository).findByUserId(userId);
    }

    @Test
    void canApprove_NoPermission() {
        // Given
        String userId = "user_001";
        String taskId = "task_001";

        when(userRoleRepository.findByUserIdAndProjectIdIsNull(userId))
                .thenReturn(Collections.emptyList()); // No global roles

        ProjectMembershipEntity membership = new ProjectMembershipEntity();
        membership.setUserId(userId);
        membership.setProjectId("project_001");
        membership.setRole("member"); // Not an admin role

        when(projectMembershipRepository.findByUserId(userId))
                .thenReturn(Arrays.asList(membership));

        // When
        boolean result = rbacService.canApprove(userId, taskId);

        // Then
        assertFalse(result);
        verify(userRoleRepository).findByUserIdAndProjectIdIsNull(userId);
        verify(projectMembershipRepository).findByUserId(userId);
    }

    @Test
    void canApprove_NoRolesOrMemberships() {
        // Given
        String userId = "user_001";
        String taskId = "task_001";

        when(userRoleRepository.findByUserIdAndProjectIdIsNull(userId))
                .thenReturn(Collections.emptyList());
        when(projectMembershipRepository.findByUserId(userId))
                .thenReturn(Collections.emptyList());

        // When
        boolean result = rbacService.canApprove(userId, taskId);

        // Then
        assertFalse(result);
        verify(userRoleRepository).findByUserIdAndProjectIdIsNull(userId);
        verify(projectMembershipRepository).findByUserId(userId);
    }

    @Test
    void hasRole_True() {
        // Given
        String userId = "user_001";
        String roleName = "admin";

        when(userRoleRepository.existsByUserIdAndRoleName(userId, roleName)).thenReturn(true);

        // When
        boolean result = rbacService.hasRole(userId, roleName);

        // Then
        assertTrue(result);
        verify(userRoleRepository).existsByUserIdAndRoleName(userId, roleName);
    }

    @Test
    void hasRole_False() {
        // Given
        String userId = "user_001";
        String roleName = "admin";

        when(userRoleRepository.existsByUserIdAndRoleName(userId, roleName)).thenReturn(false);

        // When
        boolean result = rbacService.hasRole(userId, roleName);

        // Then
        assertFalse(result);
        verify(userRoleRepository).existsByUserIdAndRoleName(userId, roleName);
    }

    @Test
    void getUserRoles() {
        // Given
        String userId = "user_001";

        UserRoleEntity role1 = new UserRoleEntity();
        role1.setRoleName("admin");
        UserRoleEntity role2 = new UserRoleEntity();
        role2.setRoleName("approver");

        when(userRoleRepository.findByUserId(userId))
                .thenReturn(Arrays.asList(role1, role2));

        // When
        Set<String> result = rbacService.getUserRoles(userId);

        // Then
        assertEquals(2, result.size());
        assertTrue(result.contains("admin"));
        assertTrue(result.contains("approver"));
        verify(userRoleRepository).findByUserId(userId);
    }

    @Test
    void getUserProjects() {
        // Given
        String userId = "user_001";

        ProjectMembershipEntity membership1 = new ProjectMembershipEntity();
        membership1.setProjectId("project_001");
        ProjectMembershipEntity membership2 = new ProjectMembershipEntity();
        membership2.setProjectId("project_002");

        when(projectMembershipRepository.findByUserId(userId))
                .thenReturn(Arrays.asList(membership1, membership2));

        // When
        Set<String> result = rbacService.getUserProjects(userId);

        // Then
        assertEquals(2, result.size());
        assertTrue(result.contains("project_001"));
        assertTrue(result.contains("project_002"));
        verify(projectMembershipRepository).findByUserId(userId);
    }
}