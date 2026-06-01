# 认证系统后端设计文档

> 生成日期: 2026-06-01
> 关联: 前端 LoginScreen 重构 + Google/GitHub OAuth + 邮箱验证码

---

## 一、现状分析

### 1.1 现有 users 表 (V7__add_auth_rbac.sql)

```sql
CREATE TABLE users (
    user_id       VARCHAR(64)  NOT NULL PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP(6) NOT NULL
);
```

**缺失字段**: email, email_verified, avatar_url, auth_provider, oauth_provider_id

### 1.2 现有认证流程

```
POST /api/v1/auth/login {username, password}
    → BCrypt 校验 → 签发 HS256 JWT (sub=username, roles=[...], exp=15min)
    → 返回 {accessToken}
```

**问题**:
- 无 OAuth 支持
- 无邮箱验证
- 无注册端点 (只能手动 INSERT 用户)
- 无刷新 Token 机制
- Token 有效期仅 15 分钟，过期后需重新登录

---

## 二、数据库变更

### 2.1 新增迁移: V15__enhance_auth_system.sql

```sql
-- ============================================================
-- V15: 认证系统增强 — OAuth + 邮箱验证码 + 刷新 Token
-- ============================================================

-- 1. 扩展 users 表
ALTER TABLE users ADD COLUMN email VARCHAR(255);
ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512);
ALTER TABLE users ADD COLUMN auth_provider VARCHAR(16) NOT NULL DEFAULT 'LOCAL';
ALTER TABLE users ADD COLUMN oauth_provider_id VARCHAR(255);
ALTER TABLE users ADD COLUMN refresh_token VARCHAR(512);
ALTER TABLE users ADD COLUMN refresh_token_expires_at TIMESTAMP(6);
ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP(6);

-- 索引: OAuth 登录通过 provider + provider_id 查找用户
CREATE UNIQUE INDEX idx_users_oauth_provider
    ON users (auth_provider, oauth_provider_id)
    WHERE oauth_provider_id IS NOT NULL;

-- 索引: 邮箱查找
CREATE INDEX idx_users_email ON users (email) WHERE email IS NOT NULL;

-- 2. 邮箱验证码表
CREATE TABLE email_verifications (
    id          VARCHAR(64)  NOT NULL PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    code        VARCHAR(6)   NOT NULL,
    purpose     VARCHAR(32)  NOT NULL DEFAULT 'LOGIN',  -- LOGIN, REGISTER
    expires_at  TIMESTAMP(6) NOT NULL,
    used        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP(6) NOT NULL
);

CREATE INDEX idx_email_verifications_email ON email_verifications (email, purpose, used);

-- 3. 用户绑定表 (一个用户可绑定多个 OAuth 提供商)
CREATE TABLE user_oauth_bindings (
    id              VARCHAR(64)  NOT NULL PRIMARY KEY,
    user_id         VARCHAR(64)  NOT NULL,
    provider        VARCHAR(16)  NOT NULL,  -- GOOGLE, GITHUB
    provider_id     VARCHAR(255) NOT NULL,
    provider_email  VARCHAR(255),
    provider_name   VARCHAR(255),
    provider_avatar VARCHAR(512),
    bound_at        TIMESTAMP(6) NOT NULL,
    CONSTRAINT fk_binding_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT uq_provider_binding UNIQUE (provider, provider_id)
);

CREATE INDEX idx_oauth_bindings_user ON user_oauth_bindings (user_id);
```

### 2.2 变更后 users 表结构

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| user_id | VARCHAR(64) | PK | 用户 ID |
| username | VARCHAR(64) | NOT NULL, UNIQUE | 用户名 (OAuth 用户用 provider_id 填充) |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 (OAuth 用户填随机值) |
| email | VARCHAR(255) | NULL | 邮箱地址 |
| email_verified | BOOLEAN | NOT NULL, DEFAULT FALSE | 邮箱是否已验证 |
| avatar_url | VARCHAR(512) | NULL | 头像 URL |
| auth_provider | VARCHAR(16) | NOT NULL, DEFAULT 'LOCAL' | 认证来源: LOCAL, GOOGLE, GITHUB, EMAIL |
| oauth_provider_id | VARCHAR(255) | NULL | OAuth 提供商的用户 ID |
| refresh_token | VARCHAR(512) | NULL | 刷新 Token |
| refresh_token_expires_at | TIMESTAMP(6) | NULL | 刷新 Token 过期时间 |
| enabled | BOOLEAN | NOT NULL, DEFAULT TRUE | 是否启用 |
| last_login_at | TIMESTAMP(6) | NULL | 最后登录时间 |
| created_at | TIMESTAMP(6) | NOT NULL | 创建时间 |

### 2.3 新增 email_verifications 表

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | PK |
| email | VARCHAR(255) | 目标邮箱 |
| code | VARCHAR(6) | 6 位验证码 |
| purpose | VARCHAR(32) | LOGIN / REGISTER |
| expires_at | TIMESTAMP(6) | 过期时间 (5 分钟) |
| used | BOOLEAN | 是否已使用 |
| created_at | TIMESTAMP(6) | 创建时间 |

### 2.4 新增 user_oauth_bindings 表

| 列名 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | PK |
| user_id | VARCHAR(64) | FK → users |
| provider | VARCHAR(16) | GOOGLE / GITHUB |
| provider_id | VARCHAR(255) | 提供商用户 ID |
| provider_email | VARCHAR(255) | 提供商邮箱 |
| provider_name | VARCHAR(255) | 提供商显示名 |
| provider_avatar | VARCHAR(512) | 提供商头像 |
| bound_at | TIMESTAMP(6) | 绑定时间 |

---

## 三、API 端点设计

### 3.1 现有端点 (保持不变)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/login` | POST | 用户名+密码登录 (已有) |

### 3.2 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/register` | POST | 邮箱注册 |
| `/api/v1/auth/email/send-code` | POST | 发送邮箱验证码 |
| `/api/v1/auth/email/verify` | POST | 邮箱验证码登录/注册 |
| `/api/v1/auth/oauth/{provider}` | GET | 发起 OAuth 授权 (重定向) |
| `/api/v1/auth/oauth/{provider}/callback` | GET | OAuth 回调处理 |
| `/api/v1/auth/refresh` | POST | 刷新 Token |
| `/api/v1/auth/logout` | POST | 注销 (撤销刷新 Token) |

### 3.3 请求/响应格式

#### POST /api/v1/auth/email/send-code

```json
// Request
{ "email": "user@example.com" }

// Response 200
{ "ok": true, "message": "验证码已发送" }

// Response 429
{ "ok": false, "message": "请 60 秒后再试" }
```

#### POST /api/v1/auth/email/verify

```json
// Request
{ "email": "user@example.com", "code": "123456" }

// Response 200
{
  "ok": true,
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2g...",
  "expiresIn": 900,
  "user": {
    "userId": "u_abc123",
    "displayName": "user",
    "email": "user@example.com",
    "avatarUrl": null,
    "provider": "EMAIL"
  }
}

// Response 401
{ "ok": false, "message": "验证码无效或已过期" }
```

#### POST /api/v1/auth/register

```json
// Request
{ "email": "user@example.com", "password": "securePass123", "displayName": "User" }

// Response 200
{
  "ok": true,
  "accessToken": "...",
  "refreshToken": "...",
  "user": { ... }
}

// Response 409
{ "ok": false, "message": "该邮箱已注册" }
```

#### GET /api/v1/auth/oauth/{provider}

```
→ 302 Redirect to:
  Google: https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&scope=email+profile
  GitHub: https://github.com/login/oauth/authorize?client_id=...&redirect_uri=...&scope=user:email
```

#### GET /api/v1/auth/oauth/{provider}/callback?code=...

```
→ 后端用 code 换 access_token
→ 获取用户信息 (email, name, avatar)
→ upsert users 表 (provider + provider_id)
→ 签发 JWT
→ 302 Redirect to: com.autocode.mobile://callback?token=...&name=...&email=...
```

#### POST /api/v1/auth/refresh

```json
// Request
{ "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2g..." }

// Response 200
{
  "ok": true,
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "refreshToken": "new_refresh_token...",
  "expiresIn": 900
}

// Response 401
{ "ok": false, "message": "刷新 Token 无效或已过期" }
```

---

## 四、OAuth 流程详细设计

### 4.1 GitHub OAuth 流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  App      │     │  Browser │     │  GitHub  │     │  Backend │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. GET /oauth/github            │                │
     │────────────────────────────────>│                │
     │                                 │                │
     │ 2. 302 → github.com/login/oauth/authorize       │
     │─────────────────────────────────────────────────>│
     │                                 │                │
     │ 3. 用户授权                      │                │
     │<────────────────────────────────│                │
     │                                 │                │
     │ 4. 回调 ?code=xxx               │                │
     │─────────────────────────────────────────────────>│
     │                                 │                │
     │                                 │ 5. POST code   │
     │                                 │    换 token    │
     │                                 │───────────────>│
     │                                 │                │
     │                                 │ 6. GET user    │
     │                                 │    info        │
     │                                 │───────────────>│
     │                                 │                │
     │                                 │ 7. upsert DB   │
     │                                 │    签发 JWT    │
     │                                 │                │
     │ 8. 302 → com.autocode.mobile://callback?token=..│
     │<────────────────────────────────────────────────│
     │                                 │                │
     │ 9. App 获取 token               │                │
     │    → 创建 Session → 主页        │                │
```

### 4.2 Google OAuth 流程

与 GitHub 类似，区别在于:
- 授权 URL: `https://accounts.google.com/o/oauth2/v2/auth`
- Token URL: `https://oauth2.googleapis.com/token`
- 用户信息: `https://www.googleapis.com/oauth2/v2/userinfo`
- Scope: `openid email profile`

---

## 五、邮箱验证码流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  App      │     │  Backend │     │  SMTP    │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     │ 1. POST /email/send-code        │
     │   {email}                        │
     │────────────────>│                │
     │                 │                │
     │                 │ 2. 生成 6 位码  │
     │                 │    存入 DB     │
     │                 │                │
     │                 │ 3. 发送邮件    │
     │                 │───────────────>│
     │                 │                │
     │ 4. {ok: true}   │                │
     │<────────────────│                │
     │                 │                │
     │ 5. POST /email/verify           │
     │   {email, code}                  │
     │────────────────>│                │
     │                 │                │
     │                 │ 6. 校验码      │
     │                 │    查 DB       │
     │                 │                │
     │                 │ 7. upsert user │
     │                 │    签发 JWT    │
     │                 │                │
     │ 8. {accessToken, refreshToken}   │
     │<────────────────│                │
```

**安全措施**:
- 验证码有效期: 5 分钟
- 同一邮箱 60 秒内只能发送一次
- 同一邮箱连续错误 5 次后锁定 15 分钟
- 验证码使用后立即标记 `used=TRUE`

---

## 六、Token 刷新机制

### 6.1 双 Token 策略

| Token | 有效期 | 用途 | 存储 |
|-------|--------|------|------|
| Access Token | 15 分钟 | API 认证 | App 内存 |
| Refresh Token | 30 天 | 刷新 Access Token | DataStore + DB |

### 6.2 刷新流程

```
App 发起 API 请求
    → 401 (Access Token 过期)
    → POST /auth/refresh {refreshToken}
    → 验证 refreshToken (DB 比对)
    → 签发新 accessToken + 新 refreshToken
    → 重试原请求
```

### 6.3 安全规则

- Refresh Token 一次性使用 (旋转刷新)
- 每次刷新签发新的 Refresh Token，旧的立即失效
- 用户注销时撤销所有 Refresh Token
- 可选: 设备绑定 (一个 Refresh Token 只能从一个设备使用)

---

## 七、配置项

```yaml
# application.yml
mvp:
  auth:
    jwt:
      secret: ${JWT_SECRET:change-me-in-production}
      access-token-ttl: 900        # 15 分钟
      refresh-token-ttl: 2592000   # 30 天
    oauth:
      google:
        client-id: ${GOOGLE_CLIENT_ID:}
        client-secret: ${GOOGLE_CLIENT_SECRET:}
        redirect-uri: ${GOOGLE_REDIRECT_URI:http://localhost:8070/api/v1/auth/oauth/google/callback}
      github:
        client-id: ${GITHUB_CLIENT_ID:}
        client-secret: ${GITHUB_CLIENT_SECRET:}
        redirect-uri: ${GITHUB_REDIRECT_URI:http://localhost:8070/api/v1/auth/oauth/github/callback}
    email:
      smtp-host: ${SMTP_HOST:smtp.gmail.com}
      smtp-port: ${SMTP_PORT:587}
      smtp-user: ${SMTP_USER:}
      smtp-pass: ${SMTP_PASS:}
      from-address: ${SMTP_FROM:noreply@autocode.dev}
      code-ttl: 300              # 5 分钟
      rate-limit-seconds: 60     # 发送间隔
```

---

## 八、实施计划

### Phase 1: 数据库 + 基础 API (优先)

| 任务 | 文件 | 说明 |
|------|------|------|
| V15 迁移 | `db/migration/V15__enhance_auth_system.sql` | 新增列 + 2 张表 |
| UserEntity 扩展 | `persistence/entity/UserEntity.java` | 新增字段映射 |
| AuthController 扩展 | `controller/AuthController.java` | 新增端点 |
| EmailVerificationService | `service/EmailVerificationService.java` | 验证码生成/校验/发送 |
| JwtService 扩展 | `service/JwtService.java` | 支持 refreshToken 签发/验证 |

### Phase 2: OAuth 集成

| 任务 | 文件 | 说明 |
|------|------|------|
| OAuth 配置 | `application.yml` | Google/GitHub client 配置 |
| OAuthService | `service/OAuthService.java` | code 换 token + 获取用户信息 |
| OAuth 回调处理 | `controller/AuthController.java` | /oauth/{provider}/callback |
| deep link 回调 | `AndroidManifest.xml` | com.autocode.mobile://callback |

### Phase 3: Token 刷新

| 任务 | 文件 | 说明 |
|------|------|------|
| RefreshTokenService | `service/RefreshTokenService.java` | 签发/验证/旋转 |
| AppViewModel 刷新逻辑 | `AppViewModel.kt` | 401 → 自动刷新 → 重试 |

---

## 九、安全注意事项

| 风险 | 缓解 |
|------|------|
| 验证码暴力破解 | 5 次错误锁定 15 分钟 |
| Refresh Token 泄露 | 一次性使用 + 旋转刷新 |
| OAuth state CSRF | 使用随机 state 参数 + 校验 |
| JWT 密钥泄露 | 使用环境变量，不硬编码 |
| 邮件轰炸 | 60 秒发送间隔 + 每日上限 |
| 明文存储 Token | 前端: EncryptedSharedPreferences (P2) |
