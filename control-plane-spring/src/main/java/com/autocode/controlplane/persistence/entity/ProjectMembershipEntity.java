package com.autocode.controlplane.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;

import java.io.Serializable;

@Entity
@Table(name = "project_memberships")
@IdClass(ProjectMembershipEntity.Pk.class)
public class ProjectMembershipEntity {
    @Id
    @Column(name = "project_id", nullable = false, length = 128)
    private String projectId;

    @Id
    @Column(name = "user_id", nullable = false, length = 64)
    private String userId;

    @Column(name = "role_name", nullable = false, length = 64)
    private String roleName;

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

    public String getRoleName() {
        return roleName;
    }

    public void setRoleName(String roleName) {
        this.roleName = roleName;
    }

    public static class Pk implements Serializable {
        private String projectId;
        private String userId;

        public Pk() {
        }

        public Pk(String projectId, String userId) {
            this.projectId = projectId;
            this.userId = userId;
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
    }
}

