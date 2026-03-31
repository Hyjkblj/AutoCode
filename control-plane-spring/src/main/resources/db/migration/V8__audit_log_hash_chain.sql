ALTER TABLE audit_logs
    ADD COLUMN prev_hash VARCHAR(64),
    ADD COLUMN entry_hash VARCHAR(64),
    ADD INDEX idx_audit_task_created_id (task_id, created_at, audit_id);

