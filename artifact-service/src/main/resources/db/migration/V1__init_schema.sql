-- Artifact Service initial schema

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id VARCHAR(64) NOT NULL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    name VARCHAR(256) NOT NULL,
    content_type VARCHAR(128),
    size_bytes BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    INDEX idx_artifacts_task_id (task_id),
    INDEX idx_artifacts_created (created_at)
);
