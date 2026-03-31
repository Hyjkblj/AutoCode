CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    project_id VARCHAR(128) NOT NULL,
    prompt TEXT NOT NULL,
    assistant VARCHAR(64) NOT NULL,
    input_mode VARCHAR(64) NOT NULL,
    risk_policy VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    assigned_node_id VARCHAR(64),
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    next_seq BIGINT NOT NULL,
    approval_id VARCHAR(64),
    approval_decision VARCHAR(32) NOT NULL,
    INDEX idx_tasks_status_created (status, created_at)
);

CREATE TABLE IF NOT EXISTS task_events (
    event_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    assistant VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_timestamp TIMESTAMP(6) NOT NULL,
    payload_json TEXT,
    seq_num BIGINT NOT NULL,
    event_version INT NOT NULL,
    INDEX idx_task_events_task_seq (task_id, seq_num),
    CONSTRAINT fk_task_events_task FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    comment_text TEXT,
    decided_at TIMESTAMP(6),
    INDEX idx_approvals_task (task_id),
    CONSTRAINT fk_approvals_task FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS agent_nodes (
    node_id VARCHAR(64) PRIMARY KEY,
    version VARCHAR(64),
    capabilities TEXT,
    last_heartbeat_at TIMESTAMP(6),
    INDEX idx_agent_nodes_heartbeat (last_heartbeat_at)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key VARCHAR(128) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    CONSTRAINT fk_idempotency_task FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64),
    actor VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    details_json TEXT,
    created_at TIMESTAMP(6) NOT NULL,
    INDEX idx_audit_task_created (task_id, created_at)
);
