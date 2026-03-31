package com.autocode.controlplane.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;

import java.io.Serializable;

@Entity
@Table(name = "user_roles")
@IdClass(UserRoleEntity.Pk.class)
public class UserRoleEntity {
    @Id
    @Column(name = "user_id", nullable = false, length = 64)
    private String userId;

    @Id
    @Column(name = "role_name", nullable = false, length = 64)
    private String roleName;

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
        private String userId;
        private String roleName;

        public Pk() {
        }

        public Pk(String userId, String roleName) {
            this.userId = userId;
            this.roleName = roleName;
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
    }
}

