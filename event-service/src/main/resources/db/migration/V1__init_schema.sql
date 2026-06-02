-- Event Service initial schema

CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR(64) NOT NULL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    assistant VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_timestamp TIMESTAMP(6) NOT NULL,
    payload_json TEXT,
    seq_num BIGINT NOT NULL,
    event_version INT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    node_id VARCHAR(64),
    INDEX idx_events_task_seq (task_id, seq_num),
    INDEX idx_events_timestamp (event_timestamp)
);
