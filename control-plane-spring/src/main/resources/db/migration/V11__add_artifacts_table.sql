CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    name VARCHAR(256) NOT NULL,
    content_type VARCHAR(128),
    size_bytes BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    INDEX idx_artifacts_task_created (task_id, created_at),
    CONSTRAINT fk_artifacts_task FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

