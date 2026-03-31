ALTER TABLE tasks
    ADD COLUMN agent_profile VARCHAR(32),
    ADD COLUMN session_key VARCHAR(128),
    ADD INDEX idx_tasks_lane_status (session_key, status);

