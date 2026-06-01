package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.EmailVerificationEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.Optional;

public interface EmailVerificationRepository extends JpaRepository<EmailVerificationEntity, String> {
    Optional<EmailVerificationEntity> findTopByEmailAndPurposeAndUsedOrderByCreatedAtDesc(
            String email, String purpose, boolean used);

    long countByEmailAndPurposeAndCreatedAtAfter(String email, String purpose, Instant since);
}
