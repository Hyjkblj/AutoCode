package com.autocode.approval.entity;

import jakarta.persistence.*;
import java.time.Instant;

/**
 * Entity representing a user's membership in a project.
 * 
 * <p>Validates: Requirements 13.2 (RBAC)
 */
@Entity
@Table(name = "project_memberships", indexes = {
    @Index(name = "idx_project_memberships_project", columnList = "project_id"),
    @Index(name = "idx_project_memberships_user", columnList = "user_id"),
    @Index(name = "idx_project_memberships_unique", columnList = "project_id,user_id", unique = true)
})
public class ProjectMembershipEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "project_id", length = 64, nullable = false)
    private String projectId;

    @Column(name = "user_id", length = 64, nullable = false)
    private String userId;

    @Column(name = "role", length = 64, nullable = false)
    private String role; // e.g., "owner", "admin", "member", "viewer"

    @Column(name = "joined_at", nullable = false)
    private Instant joinedAt;

    @Column(name = "added_by", length = 128)
    private String addedBy;

    @PrePersist
    protected void onCreate() {
        if (joinedAt == null) {
            joinedAt = Instant.now();
        }
    }

    // Getters and Setters

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public Instant getJoinedAt() {
        return joinedAt;
    }

    public void setJoinedAt(Instant joinedAt) {
        this.joinedAt = joinedAt;
    }

    public String getAddedBy() {
        return addedBy;
    }

    public void setAddedBy(String addedBy) {
        this.addedBy = addedBy;
    }
}
