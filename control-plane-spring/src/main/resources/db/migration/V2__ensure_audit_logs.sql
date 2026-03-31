CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64),
    actor VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    details_json TEXT,
    created_at TIMESTAMP(6) NOT NULL,
    INDEX idx_audit_task_created (task_id, created_at)
);
