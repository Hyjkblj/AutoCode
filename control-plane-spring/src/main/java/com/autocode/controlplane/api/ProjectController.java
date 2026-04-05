/**
 * Operator-facing project list API.
 */
package com.autocode.controlplane.api;

import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import com.autocode.controlplane.security.SecurityPrincipalUtils;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/projects")
public class ProjectController {
    private final UserEntityRepository userRepository;
    private final ProjectMembershipEntityRepository membershipRepository;

    public ProjectController(
            UserEntityRepository userRepository,
            ProjectMembershipEntityRepository membershipRepository
    ) {
        this.userRepository = userRepository;
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

        List<ProjectSummary> projects = membershipRepository.findByUserIdOrderByProjectIdAsc(userIdOpt.get()).stream()
                .map(m -> new ProjectSummary(m.getProjectId(), m.getRoleName()))
                .toList();
        return ResponseEntity.ok(ApiResponse.ok(projects));
    }

    public record ProjectSummary(String projectId, String roleName) {
    }
}
