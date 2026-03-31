CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP(6) NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    role_name VARCHAR(64) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id VARCHAR(64) NOT NULL,
    role_name VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, role_name),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_name) REFERENCES roles(role_name)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(128),
    created_at TIMESTAMP(6) NOT NULL
);

CREATE TABLE IF NOT EXISTS project_memberships (
    project_id VARCHAR(128) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    role_name VARCHAR(64) NOT NULL,
    PRIMARY KEY (project_id, user_id),
    INDEX idx_project_memberships_user (user_id),
    CONSTRAINT fk_pm_project FOREIGN KEY (project_id) REFERENCES projects(project_id),
    CONSTRAINT fk_pm_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_pm_role FOREIGN KEY (role_name) REFERENCES roles(role_name)
);

INSERT IGNORE INTO roles(role_name) VALUES ('ADMIN'), ('OPERATOR'), ('VIEWER'), ('AGENT');

