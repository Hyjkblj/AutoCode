package com.autocode.controlplane;

import com.autocode.controlplane.persistence.entity.ProjectEntity;
import com.autocode.controlplane.persistence.entity.ProjectMembershipEntity;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.ProjectEntityRepository;
import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;

import static org.hamcrest.Matchers.hasItem;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@ActiveProfiles("test")
@AutoConfigureMockMvc
class ProjectControllerIntegrationTest extends OperatorProj1MembershipFixture {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserEntityRepository userRepository;

    @Autowired
    private ProjectEntityRepository projectRepository;

    @Autowired
    private ProjectMembershipEntityRepository membershipRepository;

    @Test
    void listProjectsRequiresOperatorToken() throws Exception {
        mockMvc.perform(get("/api/v1/projects")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void listProjectsShouldReturnOnlyCurrentUserMemberships() throws Exception {
        UserEntity operator = userRepository.findByUsername("operator").orElseThrow();
        UserEntity other = ensureUser("usr_other", "other_user");

        saveProject("proj-1", "核心项目");
        saveProject("proj-2", "隔离项目");
        saveProject("proj-3", "运营项目");

        saveMembership("proj-3", operator.getUserId(), "VIEWER");
        saveMembership("proj-2", other.getUserId(), "ADMIN");

        mockMvc.perform(get("/api/v1/projects")
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.length()").value(2))
                .andExpect(jsonPath("$.payload[0].projectId").value("proj-1"))
                .andExpect(jsonPath("$.payload[0].name").value("核心项目"))
                .andExpect(jsonPath("$.payload[0].roleName").value("ADMIN"))
                .andExpect(jsonPath("$.payload[1].projectId").value("proj-3"))
                .andExpect(jsonPath("$.payload[1].name").value("运营项目"))
                .andExpect(jsonPath("$.payload[1].roleName").value("VIEWER"));
    }

    @Test
    void listProjectsShouldAllowMissingProjectNameForMembership() throws Exception {
        UserEntity operator = userRepository.findByUsername("operator").orElseThrow();
        saveMembership("proj-9", operator.getUserId(), "OPERATOR");

        mockMvc.perform(get("/api/v1/projects")
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.length()").value(2))
                .andExpect(jsonPath("$.payload[1].projectId").value("proj-9"))
                .andExpect(jsonPath("$.payload[1].name").value(org.hamcrest.Matchers.nullValue()))
                .andExpect(jsonPath("$.payload[1].roleName").value("OPERATOR"));
    }

    @Test
    void listProjectsShouldAllowNullProjectNameFromProjectRow() throws Exception {
        UserEntity operator = userRepository.findByUsername("operator").orElseThrow();
        saveProject("proj-8", null);
        saveMembership("proj-8", operator.getUserId(), "VIEWER");

        mockMvc.perform(get("/api/v1/projects")
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload[?(@.projectId=='proj-8')].name", hasItem(org.hamcrest.Matchers.nullValue())))
                .andExpect(jsonPath("$.payload[?(@.projectId=='proj-8')].roleName", hasItem("VIEWER")));
    }

    @Test
    void listProjectsShouldReturnEmptyWhenUserHasNoMembership() throws Exception {
        membershipRepository.deleteAll();

        mockMvc.perform(get("/api/v1/projects")
                        .header("Authorization", "Bearer op-a"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.payload.length()").value(0));
    }

    private UserEntity ensureUser(String userId, String username) {
        return userRepository.findByUsername(username).orElseGet(() -> {
            UserEntity user = new UserEntity();
            user.setUserId(userId);
            user.setUsername(username);
            user.setPasswordHash("x");
            user.setEnabled(true);
            user.setCreatedAt(Instant.now());
            return userRepository.save(user);
        });
    }

    private void saveMembership(String projectId, String userId, String roleName) {
        if (membershipRepository.existsByProjectIdAndUserId(projectId, userId)) {
            return;
        }
        ProjectMembershipEntity membership = new ProjectMembershipEntity();
        membership.setProjectId(projectId);
        membership.setUserId(userId);
        membership.setRoleName(roleName);
        membershipRepository.save(membership);
    }

    private void saveProject(String projectId, String name) {
        if (projectRepository.findById(projectId).isPresent()) {
            return;
        }
        ProjectEntity entity = new ProjectEntity();
        entity.setProjectId(projectId);
        entity.setName(name);
        entity.setCreatedAt(Instant.now());
        projectRepository.save(entity);
    }
}
