# AutoCode 深度架构审查报告

> 审查日期：2026-06-02
> 审查范围：整体架构、前后端交互、后端设计、前端设计、架构耦合度、数据表设计、安全性、并发控制、流量控制
> 项目规模：1659 文件，5 个 Java 微服务 + 1 个 Python Agent + 1 个 Android 原生应用

---

## 一、整体架构概览

### 1.1 系统定位

AutoCode 是一个 **AI 驱动的代码生成平台**，支持语音/文本输入 → 意图理解 → 代码规划 → 代码生成 → 审查 → 测试 → 部署的完整生命周期。

### 1.2 架构拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│           Android Mobile App (Kotlin / Jetpack Compose)          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 登录鉴权  │ │ 任务管理  │ │ 产物预览  │ │ 审批操作  │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       └────────────┼────────────┼────────────┘                  │
│                    │ HTTP/WS    │                                │
└────────────────────┼───────────┼────────────────────────────────┘
                     │           │
┌────────────────────┼───────────┼────────────────────────────────┐
│                    │   Nginx Gateway (:8080)                     │
└────────────────────┼───────────┼────────────────────────────────┘
                     │           │
          ┌──────────▼───────────▼──────────┐
          │  Operator REST API / WebSocket   │
          │   /api/v1/tasks/*   /ws          │
          └──────────┬───────────┬──────────┘
                     │           │
          ┌──────────▼───────────▼──────────┐
          │     Control Plane (:8058)        │
          │  ┌─────────┐ ┌──────────┐       │
          │  │TaskSvc  │ │EventCtrl │       │
          │  └────┬────┘ └────┬─────┘       │
          │       │           │              │
          │  ┌────▼────┐ ┌───▼──────┐       │
          │  │Redis Q  │ │MySQL/Red │       │
          │  └────┬────┘ └──────────┘       │
          └───────┼──────────────────────────┘
                  │ poll/claim
          ┌───────▼────────────┐  ┌──────────────────┐
          │  Java Agent        │  │  Python Agent     │
          │  代码执行沙箱       │  │  LLM 编排引擎     │
          └────────────────────┘  └──────────────────┘
                  │                          │
          ┌───────▼──────────────────────────▼──────┐
          │  Approval Service (:8064)                │
          │  Artifact Service (:8081)                │
          │  Event Service (:8082)                   │
          └─────────────────────────────────────────┘
                  │
          ┌───────▼──────────┐
          │  MySQL + Redis    │
          │  Prometheus/Grafana│
          └──────────────────┘
```

### 1.3 服务清单

| 服务 | 端口 | 职责 | 技术栈 |
|------|------|------|--------|
| control-plane-spring | 8058 | 核心控制平面：任务管理、事件处理、认证授权 | Spring Boot 3.3.5 / JPA / Flyway |
| pc-agent-java | - | Java Agent：代码执行沙箱、安全工具策略 | Java 17 / OkHttp |
| python-agent | - | Python Agent：LLM 调用、多 Agent 编排 | Python 3.11+ / LangGraph |
| approval-service | 8064 | 审批流程服务 | Spring Boot / JPA |
| artifact-service | 8081 | 制品存储服务 | Spring Boot / 文件系统 |
| event-service | 8082 | 事件处理服务 | Spring Boot / Redis |
| gateway | 8080 | 反向代理 | Nginx |
| mobile-app | - | Android 客户端：任务管理、审批、产物预览 | Kotlin / Jetpack Compose / OkHttp |

---

## 二、后端设计评估

### 2.1 核心设计模式

**评分：★★★★☆ (4/5)**

#### 优秀设计

1. **状态机驱动的任务生命周期**
   - `TaskStateMachine` 定义了完整的状态转换表：`QUEUED → RUNNING → WAITING_APPROVAL → DONE/FAILED/CANCELED`
   - 信息类事件（ASSISTANT_OUTPUT, TOOL_START 等）允许从任何非终态发出
   - 终态保护：只有 HEARTBEAT 可以在终态发送
   - **评价**：状态转换逻辑清晰，有独立的单元测试覆盖

2. **幂等性设计**
   - `createTask` 支持 `Idempotency-Key` header
   - 确定性 taskId：`tsk_ + sha256(idempotencyKey + projectId)` 防止并发重复
   - 数据库唯一约束 + 乐观重试处理竞态条件
   - **评价**：幂等性实现严谨，考虑了并发竞态

3. **Lease 机制的任务调度**
   - `claimQueuedTask` 使用原子 UPDATE 语句领取任务
   - Lease 过期自动回收（`recoverExpiredLeasesToQueue`）
   - Session Key 串行化：同一 session_key 不会并发执行
   - **评价**：调度机制设计合理，避免了队列抖动

4. **事件溯源 + Outbox 模式**
   - 所有任务状态变更记录为事件（TaskEventEntity）
   - Redis Outbox 保证事件至少送达一次
   - Recovery Service 处理 Agent 崩溃后的事件恢复
   - **评价**：事件可靠性设计到位

#### 待改进

1. **TaskService 职责过重** — 约 500+ 行，混合了任务创建、状态管理、事件处理、审批逻辑
2. **原生 SQL 查询较多** — `TaskEntityRepository` 中大量 `nativeQuery = true`，不利于数据库迁移
3. **事务边界模糊** — `createTask` 使用 `@Transactional(propagation = Propagation.NOT_SUPPORTED)`，手动管理事务

### 2.2 API 设计

**评分：★★★★☆ (4/5)**

#### RESTful 设计

```
POST   /api/v1/tasks              # 创建任务
GET    /api/v1/tasks              # 列出任务
GET    /api/v1/tasks/{taskId}     # 获取任务详情
GET    /api/v1/tasks/{taskId}/events    # 获取任务事件
POST   /api/v1/tasks/{taskId}/approval  # 审批任务
POST   /api/v1/tasks/{taskId}/cancel    # 取消任务
GET    /api/v1/tasks/{taskId}/artifacts/derived  # 获取衍生制品

POST   /api/v1/events/ingest      # Agent 事件上报
POST   /api/v1/auth/login         # 用户登录
POST   /api/v1/auth/agent/token   # Agent JWT 获取
```

**优点**：
- 统一的 `ApiResponse<T>` 信封格式
- `@PreAuthorize` 注解实现方法级权限控制
- 权限拒绝返回 404（防止任务存在性泄露）

**不足**：
- 缺少 API 版本化的明确策略（当前硬编码 `/api/v1/`）
- 无分页实现（`listTasks` 返回全量列表）
- 缺少 OpenAPI/Swagger 文档自动生成配置

### 2.3 数据库设计

**评分：★★★★☆ (4/5)**

#### 核心表结构

```sql
-- 核心任务表
tasks (task_id PK, session_id, project_id, prompt, assistant, status,
       assigned_node_id, workspace_path, agent_profile, session_key,
       lease_expires_at, retry_count, next_run_at, next_seq, approval_decision)

-- 事件表（事件溯源）
task_events (event_id PK, task_id FK, session_id, event_type,
             payload_json TEXT, seq_num, event_version)

-- 审批表
approvals (approval_id PK, task_id FK, decision, comment_text)

-- 用户认证
users (user_id PK, username, password_hash, enabled, email, auth_provider, ...)
user_roles (user_id FK, role_name)
user_oauth_bindings (id PK, user_id FK, provider, provider_id)
email_verifications (id PK, email, code, purpose, expires_at, used)

-- 幂等性
idempotency_records (idempotency_key PK, task_id FK)

-- 审计日志（含哈希链）
audit_logs (audit_id PK, task_id, actor, action, details_json, hash_chain)
```

**优点**：
- Flyway 版本化迁移（V1-V15），可追溯
- 索引设计合理：`idx_tasks_status_created`, `idx_task_events_task_seq`
- 审计日志哈希链防止篡改
- 唯一约束保证数据一致性

**不足**：
- `payload_json` 使用 TEXT 类型存储 JSON，无法索引查询
- 缺少软删除机制
- `agent_nodes` 表缺少资源限制字段

---

## 三、Python Agent 架构评估

**评分：★★★★☆ (4/5)**

### 3.1 Agent 编排架构

```
AgentOrchestrator (主协调器)
├── IntentAgent      # 意图识别
├── PlannerAgent     # 任务规划
├── CoderAgent       # 代码生成
├── ReviewerAgent    # 代码审查
├── TesterAgent      # 测试生成
├── DagScheduler     # DAG 调度
├── ValidationGate   # 验证门
├── DistributedTaskLock  # 分布式锁
└── LangGraphRuntime     # LangGraph 运行时
```

**优点**：
- 清晰的职责分离：每个 Agent 单一职责
- 支持两种引擎：原生 Python + LangGraph
- DAG 调度支持并行执行（max_workers=4）
- 插件化架构：PluginRegistry 支持运行时扩展

**不足**：
- `AgentOrchestrator.__init__` 参数过多（20+ 个），违反构造函数简洁原则
- Agent 间通信通过 dict 传递，缺乏类型安全
- 缺少 Agent 执行的超时熔断机制

### 3.2 LLM 集成

**评分：★★★★☆ (4/5)**

```python
class LLMClient:
    # 支持 OpenAI / Claude 双后端
    # LRU + TTL 缓存
    # 配置文件 profile 支持
    # 测试安全：pytest 中自动禁用真实调用
```

**优点**：
- 多后端支持：OpenAI / Claude / 自定义 base_url
- 响应缓存：LRU + TTL，减少重复调用
- 配置 Profile：支持 JSON 配置文件覆盖环境变量
- 测试友好：`_is_pytest_active()` 防止测试中调用真实 LLM

**不足**：
- 缺少 Token 用量统计和成本控制
- 无流式响应支持（streaming）
- 错误重试逻辑不够完善

### 3.3 可靠性机制

**评分：★★★★★ (5/5)**

这是项目中设计最好的部分：

1. **CircuitBreaker** — 标准三态实现（closed/open/half_open）
2. **DistributedTaskLock** — Redis SETNX + Lua 脚本续租/释放，自动降级到本地内存
3. **RedisOutbox** — 事件持久化 + 至少一次投递
4. **EventRecoveryService** — Agent 崩溃恢复，序列号间隙检测
5. **TaskQueueManager** — 批量处理 + 优先级队列

---

## 四、安全性评估

**评分：★★★☆☆ (3/5)**

### 4.1 认证机制

| 机制 | 用途 | 评价 |
|------|------|------|
| JWT (HS256) | 用户/Agent 认证 | ✅ 标准实现 |
| BCrypt | 密码哈希 | ✅ 安全 |
| 静态 Token | Agent 认证（过渡期） | ⚠️ 硬编码默认值 |
| mTLS | Agent 双向认证 | ✅ 可选启用 |
| OAuth 2.0 | Google/GitHub 登录 | ✅ V15 新增 |
| 邮箱验证码 | 登录/注册 | ✅ V15 新增 |

### 4.2 安全风险

#### 🔴 高风险

1. **JWT Secret 硬编码默认值**
   ```yaml
   secret: ${MVP_JWT_SECRET:autocode-dev-jwt-secret-which-is-at-least-32bytes}
   ```
   - 开发环境默认 secret 未强制覆盖
   - **建议**：启动时检测默认值并拒绝启动

2. **Agent Token 硬编码**
   ```yaml
   agent-token: ${MVP_AGENT_TOKEN:agent-dev-token}
   operator-token: ${MVP_OPERATOR_TOKEN:operator-dev-token}
   ```
   - 默认 token 值过于简单
   - **建议**：生产环境强制要求自定义 token

3. **Actuator 端点暴露**
   ```yaml
   requestMatchers("/actuator/**").permitAll()
   ```
   - 健康检查、指标、环境变量全部公开
   - **建议**：限制为内部网络或添加认证

#### 🟡 中风险

4. **CSRF 禁用**
   ```java
   csrf(csrf -> csrf.disable())
   ```
   - 理由是无状态 JWT，但 WebSocket 端点可能受影响

5. **密码错误返回信息泄露**
   ```java
   if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
       return ApiResponse.error("invalid credentials");
   }
   ```
   - 用户不存在和密码错误返回相同消息（✅ 正确）
   - 但 `user disabled` 暴露了用户存在性

6. **事件端点无认证**
   - `EventController`（event-service）的 `/events/ingest` 端点未配置认证
   - **建议**：添加 Agent Token 或 mTLS 认证

### 4.3 权限模型

```
ROLE_ADMIN    → 全局管理权限
ROLE_OPERATOR → 项目级操作权限
ROLE_AGENT    → Agent 专用权限
ROLE_VIEWER   → 只读权限

ProjectAuthz  → 项目级 ACL 检查
@PreAuthorize → 方法级权限控制
```

**优点**：
- 项目级权限隔离（`@projectAuthz.canAccessTask`）
- 权限拒绝返回 404（防止信息泄露）
- 提权权限可配置（`elevated-authorities`）

---

## 五、并发控制评估

**评分：★★★★☆ (4/5)**

### 5.1 任务调度并发

| 机制 | 实现 | 评价 |
|------|------|------|
| 任务领取 | `UPDATE ... WHERE status='QUEUED'` 原子操作 | ✅ 无竞态 |
| Lease 机制 | `lease_expires_at` + 定时回收 | ✅ 防止死锁 |
| Session 串行化 | `NOT EXISTS (SELECT 1 FROM tasks WHERE status='RUNNING' AND session_key=...)` | ✅ 防止并发冲突 |
| 幂等性 | 确定性 taskId + DB 唯一约束 | ✅ 幂等创建 |
| 分布式锁 | Redis SETNX + Lua 脚本 | ✅ 自动降级 |

### 5.2 事件处理并发

| 机制 | 实现 | 评价 |
|------|------|------|
| 事件去重 | Redis SET `event:{eventId}` + TTL | ✅ 防止重复处理 |
| 序列号 | `next_seq` 原子递增 | ✅ 保证顺序 |
| Outbox | Redis 持久化 + 后台投递 | ✅ 至少一次 |
| Recovery | 启动时扫描未确认事件 | ✅ 崩溃恢复 |

### 5.3 待改进

1. **数据库连接池未显式配置** — control-plane-spring 依赖 Spring Boot 默认值（HikariCP 默认 10）
2. **Redis 连接池配置不足** — event-service 配置了 Lettuce pool，但 control-plane-spring 未配置
3. **缺少全局并发限制** — 无任务执行的全局并发上限

---

## 六、流量控制评估

**评分：★★★☆☆ (3/5)**

### 6.1 现有机制

| 机制 | 状态 | 评价 |
|------|------|------|
| CircuitBreaker | ✅ Python Agent 实现 | 事件投递熔断 |
| Lease 超时 | ✅ 60 秒默认 | 防止任务无限占用 |
| 重试退避 | ✅ 指数退避 | `retryBaseBackoffSeconds` |
| 请求超时 | ✅ Python Agent 15 秒 | HTTP 客户端超时 |
| 文件大小限制 | ✅ 512MB | 制品上传限制 |

### 6.2 缺失机制

1. **无 API 限流（Rate Limiting）**
   - 没有基于 IP/User/API Key 的请求频率限制
   - **建议**：使用 Bucket4j 或 Resilience4j 实现限流

2. **无全局任务并发限制**
   - Agent 可以同时执行无限数量的任务
   - **建议**：添加 `max-concurrent-tasks` 配置

3. **无 LLM 调用限流**
   - Python Agent 对 LLM API 的调用没有频率/Token 限制
   - **建议**：添加 Token Bucket 或滑动窗口限流

4. **缺少背压（Backpressure）机制**
   - 任务队列无上限，可能导致内存溢出
   - **建议**：Redis List 添加 MAXLEN 限制

---

## 七、架构耦合度评估

**评分：★★★★☆ (4/5)**

### 7.1 耦合分析

```
耦合度矩阵：
                    ControlPlane  EventService  ApprovalService  ArtifactService  PythonAgent
ControlPlane        -             中(共享DB)     低               中(制品查询)      低(HTTP)
EventService        中(共享Redis)  -             低               低               低
ApprovalService     低             低            -                低               低
ArtifactService     中(认证依赖)   低            低               -                低
PythonAgent         低(HTTP)       低            低               低               -
```

### 7.2 优点

1. **shared-protocol 模块** — 共享的协议定义（TaskStatus, EventType, EventAckResponse）
2. **六边形架构** — `TaskReadPort` / `TaskQueuePort` 接口抽象
3. **配置驱动** — 服务间通信通过配置注入 URL
4. **事件驱动** — 服务间通过事件异步通信

### 7.3 不足

1. **数据库耦合** — control-plane 和 event-service 共享同一个 MySQL 实例（可配置但默认如此）
2. **Redis 耦合** — 多个服务共享同一个 Redis 实例
3. **认证耦合** — artifact-service 依赖 control-plane 进行认证
4. **Python Agent 与 Java Agent 共享文件系统** — `network_mode: "service:pc-agent-java"` + 共享 volume

---

## 八、前端设计评估

**评分：★★★★☆ (4/5)**

### 8.1 技术栈

| 维度 | 选型 | 评价 |
|------|------|------|
| 平台 | Android 原生 | ✅ 语音输入、通知推送等原生能力 |
| UI 框架 | Jetpack Compose (Material 3) | ✅ 声明式 UI，现代化 |
| 语言 | Kotlin 2.0.21 | ✅ 类型安全 |
| 网络层 | OkHttp 4.12 | ✅ 成熟稳定 |
| 序列化 | kotlinx-serialization | ✅ 编译期生成，无反射 |
| 本地存储 | DataStore Preferences + Room | ✅ 轻量 KV + 结构化缓存 |
| 导航 | Navigation Compose | ✅ 官方方案 |
| WebSocket | 自实现 STOMP 客户端 | ⚠️ 见下方分析 |
| Markdown | multiplatform-markdown-renderer | ✅ 代码高亮 + 图片 |
| 最低版本 | Android 8.0 (API 26) | ✅ 覆盖率 ~95% |

### 8.2 应用架构

```
MainActivity
└── AutoCodeApp()
    ├── LoginRoute          — 用户名/密码登录 + 控制面地址配置
    └── MainShell           — 底部导航栏
        ├── HomeTab         — 首页概览（登录状态、项目、生成目标）
        ├── TaskListTab     — 任务列表 + 语音/文本输入创建任务
        │   └── TaskDetailTab — 任务详情（实时事件流 + 审批）
        ├── ArtifactsHubTab — 产物中心
        │   ├── ArtifactsForTaskScreen — 任务产物列表
        │   ├── ArtifactDetailScreen   — 产物详情（预览/发布/访问链接）
        │   └── PublishHistoryScreen   — 发布历史
        ├── ProjectsTab     — 项目选择（远程 + 本地兜底）
        └── AccountTab      — 设置（连接配置、生成目标、代理身份、通知、节点状态）
```

### 8.3 核心功能评估

#### 8.3.1 任务生命周期管理

**评分：★★★★★ (5/5)**

- **创建任务**：支持文本输入 + Android 语音识别（`RecognizerIntent`）
- **实时事件流**：WebSocket STOMP 订阅 `/topic/tasks/{taskId}`，自动重连（指数退避，最大 30 秒）
- **事件回填**：WebSocket 连接前先 HTTP 拉取历史事件，保证完整性
- **事件缓存**：Room 数据库本地缓存事件（每任务 300 条，全局 4000 条），应用重启后可恢复
- **审批操作**：`ModalBottomSheet` 展示审批详情，支持批准/拒绝/超时自动处理
- **状态同步**：3.5 秒轮询远程任务状态 + WebSocket 实时推送双通道

**亮点**：
- `eventStableKey` 保证事件去重（eventId > seq > composite key）
- 事件合并时自动更新任务状态和进度
- 断线重连后自动回填丢失事件

#### 8.3.2 产物管理

**评分：★★★★☆ (4/5)**

- **产物列表**：按已完成任务分组展示
- **在线预览**：支持文本文件 + ZIP 文件（自动解压展示目录结构和文本样本）
- **访问链接**：生成/短链/分享链接三种入口
- **发布操作**：填写版本号 + 环境 → 创建 Deploy 任务
- **发布历史**：本地持久化 + 远程同步，展示状态/环境/访问地址

**亮点**：
- ZIP 预览支持条目列表 + 文本样本采样（最大 8KB）
- 自动检测 UTF-8 Mojibake 编码问题并修复
- Diff 预览支持中文本地化（`diff --git` → `文件差异`）

#### 8.3.3 通知系统

**评分：★★★★☆ (4/5)**

- **通知渠道**：`agent_task_approvals`（高优先级）+ `agent_task_updates`（普通优先级）
- **触发事件**：审批待处理、任务完成、任务失败、计划审批
- **去重机制**：`recentNotificationKeys` 队列（200 条），防止重复通知
- **权限处理**：Android 13+ 自动请求 `POST_NOTIFICATIONS` 权限

#### 8.3.4 网络层

**评分：★★★★☆ (4/5)**

**ControlPlaneClient**（HTTP）：
- 统一的 `ApiResponse` 信封解析（`ok` + `payload` + `error`）
- 自动处理 404/405 兼容旧版控制面
- 超时配置：连接/读/写各 30 秒
- 认证失败自动登出（`handleAuthExpired`）

**WebSocketClient**（实时）：
- STOMP 1.2 协议实现
- 自动重连：指数退避（2^n 秒，最大 30 秒）
- 心跳：10 秒间隔
- 认证失败检测：15 种错误模式匹配

### 8.4 数据流设计

```
┌──────────────┐     HTTP      ┌──────────────┐
│  ControlPlane │◄────────────►│  AppViewModel │
│  Client       │              │  (StateFlow)  │
└──────────────┘              │               │
                               │  ┌─────────┐  │
┌──────────────┐   WebSocket   │  │DataStore│  │ 持久化
│  WebSocket   │──────────────►│  │(Prefs)  │  │
│  Client       │   STOMP      │  └─────────┘  │
└──────────────┘              │               │
                               │  ┌─────────┐  │
                               │  │  Room   │  │ 事件缓存
                               │  │  DB     │  │
                               │  └─────────┘  │
                               └───────┬───────┘
                                       │ StateFlow
                               ┌───────▼───────┐
                               │  Compose UI   │
                               │  (collectAs   │
                               │   StateWith   │
                               │   Lifecycle)  │
                               └───────────────┘
```

### 8.5 代码质量评估

#### 优点

1. **单一数据源** — `AppViewModel` 通过 `MutableStateFlow<UiState>` 驱动整个 UI
2. **生命周期感知** — `collectAsStateWithLifecycle` 自动管理订阅
3. **离线优先** — 无控制面地址时自动降级到本地模拟模式
4. **类型安全** — kotlinx-serialization 编译期序列化
5. **测试标签** — `MobileUiTestTags` 定义了关键 UI 元素的 testTag

#### 待改进

1. **ViewModel 职责过重** — `AppViewModel.kt` 约 1800+ 行，混合了网络、持久化、通知、状态管理
2. **无依赖注入** — 使用 `ViewModelProvider.Factory` 手动创建，未使用 Hilt/Koin
3. **硬编码 Mock** — `mockProjects` 硬编码了 3 个项目
4. **无 UI 测试** — 仅有 1 个 `CriticalUiRegressionTest.kt`，缺少 Compose UI 测试覆盖
5. **无单元测试** — ViewModel 逻辑无单元测试

### 8.6 前后端交互评估

| 交互模式 | 实现 | 评价 |
|----------|------|------|
| REST API | OkHttp 同步调用 + Dispatchers.IO | ✅ 标准实现 |
| WebSocket | STOMP 1.2 over OkHttp | ✅ 自动重连 |
| 事件回填 | HTTP GET `/events?lastSeq=N` | ✅ 断线恢复 |
| 审批提交 | POST `/tasks/{id}/approval` | ✅ 标准 REST |
| 产物下载 | GET `/artifacts/{id}/download` | ✅ 二进制支持 |
| 认证 | JWT Bearer Token | ✅ 标准方案 |
| 离线模式 | 本地模拟 + DataStore 持久化 | ✅ 用户体验好 |

### 8.7 前端评分汇总

| 维度 | 评分 | 说明 |
|------|------|------|
| UI/UX 设计 | 4/5 | Material 3 + 底部导航 + 实时事件流 |
| 架构设计 | 4/5 | MVVM + StateFlow，但 ViewModel 过大 |
| 网络层 | 4/5 | HTTP + WebSocket 双通道，自动重连 |
| 离线能力 | 5/5 | 本地模拟 + 事件缓存 + 状态恢复 |
| 代码质量 | 3/5 | 缺少测试覆盖和依赖注入 |
| 性能优化 | 4/5 | Room 缓存 + 分页裁剪 + 延迟加载 |

---

## 九、可观测性评估

**评分：★★★★★ (5/5)**

### 9.1 指标体系

```java
// ControlPlaneMetrics — 核心业务指标
mvp_tasks_created_total          // 任务创建数
mvp_tasks_polled_total           // 任务领取数
mvp_task_events_ingested_total   // 事件处理数
mvp_task_events_duplicate_total  // 重复事件数
mvp_task_illegal_transition_total // 非法状态转换数
mvp_task_ack_failures_total      // ACK 失败数
mvp_task_lease_requeued_total    // Lease 回收数
mvp_task_poll_duration           // 轮询耗时
```

### 9.2 监控栈

- **Prometheus** — 指标采集
- **Grafana** — 可视化仪表盘
- **Alertmanager** — 告警通知
- **Micrometer** — Spring Boot 指标桥接
- **OpenTelemetry** — 分布式追踪（可选）

### 9.3 健康检查

- `/actuator/health` — Spring Boot 标准健康检查
- `/events/health` — Event Service 自定义健康检查（含 Redis 连通性）
- Kubernetes 就绪/存活探针支持

---

## 十、测试覆盖评估

**评分：★★★★★ (5/5)**

### 10.1 测试统计

| 模块 | 测试文件数 | 测试类型 |
|------|-----------|---------|
| control-plane-spring | 30+ | 单元/集成/属性测试 |
| python-agent | 80+ | 单元/集成/属性/E2E 测试 |
| 总计 | 110+ | 覆盖率报告生成 |

### 10.2 测试亮点

1. **属性测试（Property-based Testing）**
   - 使用 jqwik 进行属性测试
   - 覆盖：事件去重、缓存命中率、熔断器、超时等

2. **E2E 测试**
   - `e2e_real_chain.py` — 真实 LLM 调用的端到端测试
   - `test_e2e_task_lifecycle.py` — 任务生命周期测试

3. **混沌测试**
   - `test_circuit_breaker_comprehensive.py` — 熔断器混沌测试
   - `test_recovery_service.py` — 崩溃恢复测试

---

## 十一、综合评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 整体架构 | ★★★★☆ | 微服务划分合理，事件驱动架构成熟 |
| 后端设计 | ★★★★☆ | 状态机/幂等性/Lease 设计优秀 |
| 前端设计 | ★★★★☆ | Android 原生 + Compose + 实时事件流 + 离线优先 |
| 架构耦合度 | ★★★★☆ | 接口抽象良好，少量基础设施耦合 |
| 数据表设计 | ★★★★☆ | 版本化迁移，索引合理 |
| 安全性 | ★★★☆☆ | 默认配置风险，部分端点未认证 |
| 并发控制 | ★★★★☆ | 原子操作+分布式锁，缺少全局限制 |
| 流量控制 | ★★★☆☆ | 缺少限流和背压机制 |
| 可观测性 | ★★★★★ | 完整的指标+监控+告警体系 |
| 测试覆盖 | ★★★★★ | 属性测试+E2E+混沌测试 |

**综合评分：★★★★☆ (4.1/5)**

---

## 十二、改进建议优先级

### 🔴 P0 — 安全性（立即修复）

1. 启动时检测并拒绝默认 JWT Secret
2. Actuator 端点添加认证或限制访问
3. Event Service 端点添加 Agent 认证

### 🟡 P1 — 流量控制（1-2 周）

4. 添加 API Rate Limiting（推荐 Bucket4j）
5. 添加全局任务并发限制
6. LLM 调用 Token Bucket 限流

### 🟢 P2 — 架构优化（1-2 月）

7. TaskService 拆分：TaskCreationService / TaskLifecycleService / TaskEventService
8. AppViewModel 拆分：提取 NetworkRepository / TaskRepository / NotificationManager
9. 数据库连接池显式配置
10. API 分页支持
11. OpenAPI 文档自动生成
12. 引入 Hilt 依赖注入 + ViewModel 单元测试覆盖

### 🔵 P3 — 长期演进

12. 服务网格（Istio）替代手动 mTLS
13. 分布式追踪全链路覆盖
14. LLM 流式响应支持
15. 多租户支持

---

## 附录 A：技术栈清单

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | Spring Boot | 3.3.5 |
| Java | JDK | 17+ |
| Python | CPython | 3.11+ |
| 移动端 | Kotlin + Jetpack Compose | 2.0.21 |
| 数据库 | MySQL | 8.4 |
| 缓存 | Redis | 7.4 |
| ORM | Hibernate/JPA | 6.x |
| 数据库迁移 | Flyway | 最新 |
| HTTP 客户端 | OkHttp | 4.12.0 |
| 消息队列 | Redis List | - |
| API 网关 | Nginx | 1.27 |
| 监控 | Prometheus + Grafana | 2.54 / 11.1 |
| 容器化 | Docker Compose | - |
| LLM 后端 | OpenAI / Claude | - |
| Agent 框架 | LangGraph | - |

## 附录 B：关键文件索引

| 文件 | 职责 |
|------|------|
| `control-plane-spring/.../TaskService.java` | 核心任务服务 |
| `control-plane-spring/.../TaskStateMachine.java` | 状态机定义 |
| `control-plane-spring/.../JwtSecurityConfig.java` | 安全配置 |
| `control-plane-spring/.../TaskEntityRepository.java` | 数据访问层 |
| `python-agent/orchestrator/agent_orchestrator.py` | Agent 编排器 |
| `python-agent/llm/llm_client.py` | LLM 客户端 |
| `python-agent/utils/circuit_breaker.py` | 熔断器 |
| `python-agent/orchestrator/distributed_lock.py` | 分布式锁 |
| `python-agent/outbox/recovery_service.py` | 事件恢复服务 |
| `control-plane-spring/.../RedisBackedTaskQueue.java` | Redis 任务队列 |
| `mobile-app/.../AppViewModel.kt` | 前端核心 ViewModel（1800+ 行） |
| `mobile-app/.../AppUi.kt` | 前端 Compose UI（1200+ 行） |
| `mobile-app/.../network/ControlPlaneClient.kt` | 前端 HTTP 客户端 |
| `mobile-app/.../network/WebSocketClient.kt` | 前端 WebSocket STOMP 客户端 |
| `mobile-app/.../Models.kt` | 前端数据模型 |
