package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.ArtifactEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ArtifactEntityRepository extends JpaRepository<ArtifactEntity, String> {
    List<ArtifactEntity> findByTaskIdOrderByCreatedAtDesc(String taskId);
}

