package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.UserRoleEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface UserRoleEntityRepository extends JpaRepository<UserRoleEntity, UserRoleEntity.Pk> {
    List<UserRoleEntity> findByUserId(String userId);
}

