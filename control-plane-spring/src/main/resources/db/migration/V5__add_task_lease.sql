ALTER TABLE tasks
    ADD COLUMN leased_at TIMESTAMP(6),
    ADD COLUMN lease_expires_at TIMESTAMP(6),
    ADD INDEX idx_tasks_lease_expires (lease_expires_at);

