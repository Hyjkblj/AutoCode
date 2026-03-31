package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.UserEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserEntityRepository extends JpaRepository<UserEntity, String> {
    Optional<UserEntity> findByUsername(String username);
}

