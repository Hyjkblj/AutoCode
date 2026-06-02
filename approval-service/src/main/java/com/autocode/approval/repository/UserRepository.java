package com.autocode.approval.repository;

import com.autocode.approval.entity.UserEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Repository for user entities.
 */
@Repository
public interface UserRepository extends JpaRepository<UserEntity, String> {

    /**
     * Find user by username.
     */
    Optional<UserEntity> findByUsername(String username);

    /**
     * Find user by email.
     */
    Optional<UserEntity> findByEmail(String email);

    /**
     * Check if username exists.
     */
    boolean existsByUsername(String username);

    /**
     * Check if email exists.
     */
    boolean existsByEmail(String email);
}
