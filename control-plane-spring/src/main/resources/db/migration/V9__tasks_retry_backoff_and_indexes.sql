ALTER TABLE tasks
    ADD COLUMN retry_count INT NOT NULL DEFAULT 0,
    ADD COLUMN next_run_at TIMESTAMP(6),
    ADD INDEX idx_tasks_profile_status_created (agent_profile, status, created_at),
    ADD INDEX idx_tasks_status_next_run (status, next_run_at, created_at);

