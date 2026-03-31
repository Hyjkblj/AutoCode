package com.autocode.controlplane.security;

import com.autocode.controlplane.persistence.entity.TaskEntity;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.TaskEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

import java.util.Optional;

@Component("projectAuthz")
public class ProjectAuthz {
    private final UserEntityRepository userRepository;
    private final ProjectMembershipEntityRepository membershipRepository;
    private final TaskEntityRepository taskRepository;

    public ProjectAuthz(
            UserEntityRepository userRepository,
            ProjectMembershipEntityRepository membershipRepository,
            TaskEntityRepository taskRepository
    ) {
        this.userRepository = userRepository;
        this.membershipRepository = membershipRepository;
        this.taskRepository = taskRepository;
    }

    public boolean canAccessProject(String projectId) {
        if (projectId == null || projectId.isBlank()) return false;
        if (isAdmin()) return true;
        String username = SecurityPrincipalUtils.currentUsernameOrNull();
        if (username == null) return false;
        Optional<UserEntity> user = userRepository.findByUsername(username);
        return user.isPresent() && membershipRepository.existsByProjectIdAndUserId(projectId, user.get().getUserId());
    }

    public boolean canAccessTask(String taskId) {
        if (taskId == null || taskId.isBlank()) return false;
        if (isAdmin()) return true;
        String username = SecurityPrincipalUtils.currentUsernameOrNull();
        if (username == null) return false;
        Optional<UserEntity> user = userRepository.findByUsername(username);
        if (user.isEmpty()) return false;
        Optional<TaskEntity> taskOpt = taskRepository.findById(taskId);
        if (taskOpt.isEmpty()) return false;
        String projectId = taskOpt.get().getProjectId();
        return membershipRepository.existsByProjectIdAndUserId(projectId, user.get().getUserId());
    }

    private boolean isAdmin() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) return false;
        return auth.getAuthorities().stream().anyMatch(a ->
                "ROLE_ADMIN".equals(a.getAuthority()) || "ROLE_OPERATOR".equals(a.getAuthority())
        );
    }
}

