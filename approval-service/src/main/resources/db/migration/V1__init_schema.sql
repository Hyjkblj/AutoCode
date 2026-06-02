-- Approval Service initial schema

CREATE TABLE IF NOT EXISTS approvals (
    approval_id VARCHAR(64) NOT NULL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    trace_id VARCHAR(128),
    run_id VARCHAR(128),
    action VARCHAR(128),
    tool VARCHAR(128),
    command TEXT,
    workspace_ref VARCHAR(512),
    reason TEXT,
    risk_score DOUBLE,
    required_policies TEXT,
    context_json TEXT,
    decision VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    decision_message TEXT,
    decided_by VARCHAR(128),
    decided_at TIMESTAMP(6),
    timeout_seconds INT,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    INDEX idx_approvals_task_id (task_id),
    INDEX idx_approvals_status (decision),
    INDEX idx_approvals_created (created_at)
);

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) NOT NULL PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    email VARCHAR(256) NOT NULL UNIQUE,
    display_name VARCHAR(256),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email)
);

CREATE TABLE IF NOT EXISTS user_roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    role_name VARCHAR(64) NOT NULL,
    project_id VARCHAR(64),
    granted_at TIMESTAMP(6) NOT NULL,
    granted_by VARCHAR(128),
    INDEX idx_user_roles_user_id (user_id),
    INDEX idx_user_roles_role (role_name)
);

CREATE TABLE IF NOT EXISTS project_memberships (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    role VARCHAR(64) NOT NULL,
    joined_at TIMESTAMP(6) NOT NULL,
    added_by VARCHAR(128),
    INDEX idx_project_memberships_project (project_id),
    INDEX idx_project_memberships_user (user_id),
    UNIQUE INDEX idx_project_memberships_unique (project_id, user_id)
);
