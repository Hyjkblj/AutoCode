-- V15: 认证系统增强 — OAuth + 邮箱验证码 + 刷新 Token

-- 1. 扩展 users 表
ALTER TABLE users ADD COLUMN email VARCHAR(255);
ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512);
ALTER TABLE users ADD COLUMN auth_provider VARCHAR(16) NOT NULL DEFAULT 'LOCAL';
ALTER TABLE users ADD COLUMN oauth_provider_id VARCHAR(255);
ALTER TABLE users ADD COLUMN refresh_token VARCHAR(512);
ALTER TABLE users ADD COLUMN refresh_token_expires_at TIMESTAMP(6);
ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP(6);

-- MySQL不支持部分索引，使用普通索引代替
CREATE INDEX idx_users_oauth_provider
    ON users (auth_provider, oauth_provider_id);

CREATE INDEX idx_users_email ON users (email);

-- 2. 邮箱验证码表
CREATE TABLE email_verifications (
    id          VARCHAR(64)  NOT NULL PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    code        VARCHAR(6)   NOT NULL,
    purpose     VARCHAR(32)  NOT NULL DEFAULT 'LOGIN',
    expires_at  TIMESTAMP(6) NOT NULL,
    used        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP(6) NOT NULL
);

CREATE INDEX idx_email_verifications_email ON email_verifications (email, purpose, used);

-- 3. 用户 OAuth 绑定表
CREATE TABLE user_oauth_bindings (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    user_id         VARCHAR(64)  NOT NULL,
    provider        VARCHAR(16)  NOT NULL,
    provider_id     VARCHAR(255) NOT NULL,
    provider_email  VARCHAR(255),
    provider_name   VARCHAR(255),
    provider_avatar VARCHAR(512),
    bound_at        TIMESTAMP(6) NOT NULL,
    CONSTRAINT fk_binding_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT uq_provider_binding UNIQUE (provider, provider_id)
);

CREATE INDEX idx_oauth_bindings_user ON user_oauth_bindings (user_id);
