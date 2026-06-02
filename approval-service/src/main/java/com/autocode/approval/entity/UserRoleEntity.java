package com.autocode.approval.entity;

import jakarta.persistence.*;
import java.time.Instant;

/**
 * Entity representing a user's role assignment.
 * 
 * <p>Validates: Requirements 13.2 (RBAC)
 */
@Entity
@Table(name = "user_roles", indexes = {
    @Index(name = "idx_user_roles_user_id", columnList = "user_id"),
    @Index(name = "idx_user_roles_role", columnList = "role_name")
})
public class UserRoleEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "user_id", length = 64, nullable = false)
    private String userId;

    @Column(name = "role_name", length = 64, nullable = false)
    private String roleName;

    @Column(name = "project_id", length = 64)
    private String projectId; // null for global roles

    @Column(name = "granted_at", nullable = false)
    private Instant grantedAt;

    @Column(name = "granted_by", length = 128)
    private String grantedBy;

    @PrePersist
    protected void onCreate() {
        if (grantedAt == null) {
            grantedAt = Instant.now();
        }
    }

    // Getters and Setters

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getRoleName() {
        return roleName;
    }

    public void setRoleName(String roleName) {
        this.roleName = roleName;
    }

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public Instant getGrantedAt() {
        return grantedAt;
    }

    public void setGrantedAt(Instant grantedAt) {
        this.grantedAt = grantedAt;
    }

    public String getGrantedBy() {
        return grantedBy;
    }

    public void setGrantedBy(String grantedBy) {
        this.grantedBy = grantedBy;
    }
}
