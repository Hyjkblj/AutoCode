package com.autocode.controlplane.persistence.repo;

import com.autocode.controlplane.persistence.entity.ProjectEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ProjectEntityRepository extends JpaRepository<ProjectEntity, String> {
    List<ProjectEntity> findByProjectIdIn(List<String> projectIds);
}
