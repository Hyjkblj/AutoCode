package com.autocode.artifact;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Spring Data JPA repository for {@link ArtifactEntity}.
 *
 * Requirements: 14.1, 14.4
 */
@Repository
public interface ArtifactRepository extends JpaRepository<ArtifactEntity, String> {

    /**
     * Returns all artifacts for a given task, newest first.
     *
     * @param taskId the owning task identifier
     * @return ordered list of artifact entities
     */
    List<ArtifactEntity> findByTaskIdOrderByCreatedAtDesc(String taskId);

    /**
     * Checks whether any artifact exists for the given task.
     *
     * @param taskId the owning task identifier
     * @return {@code true} if at least one artifact is stored for the task
     */
    boolean existsByTaskId(String taskId);
}
