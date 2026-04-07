/**
 * Operator-facing project list API.
 */
package com.autocode.controlplane.api;

import com.autocode.controlplane.persistence.entity.ProjectMembershipEntity;
import com.autocode.controlplane.persistence.repo.ProjectEntityRepository;
import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import com.autocode.controlplane.security.SecurityPrincipalUtils;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/projects")
public class ProjectController {
    private final UserEntityRepository userRepository;
    private final ProjectEntityRepository projectRepository;
    private final ProjectMembershipEntityRepository membershipRepository;

    public ProjectController(
            UserEntityRepository userRepository,
            ProjectEntityRepository projectRepository,
            ProjectMembershipEntityRepository membershipRepository
    ) {
        this.userRepository = userRepository;
        this.projectRepository = projectRepository;
        this.membershipRepository = membershipRepository;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<ProjectSummary>>> listProjects() {
        String username = SecurityPrincipalUtils.currentUsernameOrNull();
        if (username == null) {
            return ResponseEntity.ok(ApiResponse.ok(List.of()));
        }

        Optional<String> userIdOpt = userRepository.findByUsername(username).map(user -> user.getUserId());
        if (userIdOpt.isEmpty()) {
            return ResponseEntity.ok(ApiResponse.ok(List.of()));
        }

        List<ProjectMembershipEntity> memberships = membershipRepository.findByUserIdOrderByProjectIdAsc(userIdOpt.get());
        if (memberships.isEmpty()) {
            return ResponseEntity.ok(ApiResponse.ok(List.of()));
        }

        List<String> projectIds = memberships.stream()
                .map(ProjectMembershipEntity::getProjectId)
                .distinct()
                .toList();
        Map<String, String> projectNameById = projectRepository.findByProjectIdIn(projectIds).stream()
                .collect(Collectors.toMap(
                        p -> p.getProjectId(),
                        p -> p.getName(),
                        (a, b) -> a
                ));

        List<ProjectSummary> projects = memberships.stream()
                .map(m -> new ProjectSummary(
                        m.getProjectId(),
                        projectNameById.get(m.getProjectId()),
                        m.getRoleName()
                ))
                .toList();
        return ResponseEntity.ok(ApiResponse.ok(projects));
    }

    public record ProjectSummary(String projectId, String name, String roleName) {
    }
}
