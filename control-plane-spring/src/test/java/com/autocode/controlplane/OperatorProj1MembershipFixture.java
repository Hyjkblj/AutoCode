package com.autocode.controlplane;

import com.autocode.controlplane.persistence.entity.ProjectMembershipEntity;
import com.autocode.controlplane.persistence.entity.UserEntity;
import com.autocode.controlplane.persistence.repo.ProjectMembershipEntityRepository;
import com.autocode.controlplane.persistence.repo.UserEntityRepository;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;

import java.time.Instant;

/**
 * Token mode maps every operator bearer token to principal {@code operator}; project-scoped APIs
 * require a membership row for tests that use {@code projectId=proj-1}.
 */
public abstract class OperatorProj1MembershipFixture {

    @Autowired
    private UserEntityRepository userRepository;

    @Autowired
    private ProjectMembershipEntityRepository membershipRepository;

    @BeforeEach
    void seedOperatorMembershipForProj1() {
        UserEntity user = userRepository.findByUsername("operator").orElseGet(() -> {
            UserEntity u = new UserEntity();
            u.setUserId("usr_operator");
            u.setUsername("operator");
            u.setPasswordHash("x");
            u.setEnabled(true);
            u.setCreatedAt(Instant.now());
            return userRepository.save(u);
        });

        if (!membershipRepository.existsByProjectIdAndUserId("proj-1", user.getUserId())) {
            ProjectMembershipEntity membership = new ProjectMembershipEntity();
            membership.setProjectId("proj-1");
            membership.setUserId(user.getUserId());
            membership.setRoleName("ADMIN");
            membershipRepository.save(membership);
        }
    }
}
