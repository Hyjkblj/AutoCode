# AutoCode

**AI-Powered Code Generation Platform** - 从自然语言描述自动生成可运行的Web应用

AutoCode是一个多智能体协作的代码生成平台，支持从自然语言描述自动生成完整的Web应用。用户只需描述想要的功能，系统会自动生成HTML/CSS/JavaScript代码，并打包为可部署的产物。

## 核心特性

- **自然语言驱动**: 用中文或英文描述需求，自动生成代码
- **多智能体协作**: Intent → Planner → Coder → Reviewer 流水线
- **实时预览**: 生成的Web应用可直接在浏览器中预览
- **安全沙箱**: 命令执行在隔离的沙箱环境中运行
- **移动端支持**: 提供Android移动客户端

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend / Mobile                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Control Plane (Spring)                        │
│  - REST API / WebSocket                                          │
│  - Task Lifecycle Management                                     │
│  - Authentication & Authorization                                │
│  - Artifact Storage & Hosting                                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│   Python Agent    │ │   Java Agent    │ │   Shared Protocol   │
│ - Intent Analysis │ │ - Sandbox Exec  │ │ - Event Contracts   │
│ - Plan Generation │ │ - Command Policy│ │ - DTO Definitions   │
│ - Code Generation │ │ - Security Gate │ │ - JSON Validators   │
└───────────────────┘ └─────────────────┘ └─────────────────────┘
```

## 模块说明

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| `control-plane-spring` | Spring Boot 3.x | 控制平面，负责任务调度、状态管理、权限控制 |
| `pc-agent-java` | Java 17+ | 执行代理，提供安全沙箱和命令执行能力 |
| `python-agent` | Python 3.11+ | AI编排代理，负责意图识别、代码生成 |
| `shared-protocol` | Java | 跨语言协议定义，确保组件间通信一致性 |
| `mobile-app` | Kotlin/Android | 移动端应用，支持语音输入和实时预览 |

### control-plane-spring

- REST + STOMP/WebSocket 控制平面
- 任务生命周期/状态机管理
- 审批流程、审计链、产物管理、RBAC权限
- MySQL持久化 + Redis队列支持

### pc-agent-java

- 命令执行节点运行时
- 基于策略的安全门控 + 审批等待
- 本地沙箱HTTP API (`/sandbox/*`)
- 产物/运行时元数据上报

### python-agent

- AI工作流编排 (`Intent -> Planner -> Coder -> Reviewer/Tester`)
- DAG并行阶段调度
- Redis支持的内存存储（支持内存回退）
- 调用Java沙箱执行命令/测试/部署

### shared-protocol

- 共享DTO定义 (`TaskEvent`, `SandboxExecuteRequest/Response`, `ArtifactMetadata`, ...)
- JSON Schema对齐的事件/沙箱/清单验证器

### mobile-app

- Android原生应用
- 支持语音输入描述需求
- 实时查看生成进度和产物预览
- 任务历史管理

## 端到端流程

```
用户输入 → IntentAgent(意图识别) → PlannerAgent(计划生成) → CoderAgent(代码生成) → 产物打包 → 用户预览
```

详细步骤：

1. 用户创建任务 (`POST /api/v1/tasks`)，提供自然语言描述
2. 控制平面持久化任务状态为 `QUEUED`，发送 `TASK_CREATED` 事件
3. Python Agent轮询获取任务 (`GET /api/v1/agent/tasks/next`)
4. Agent执行并流式发送事件：
   - `ASSISTANT_OUTPUT`: 阶段进度更新
   - `FILE_PATCH_PREVIEW`: 文件变更预览
   - `ARTIFACT_READY`: 产物就绪
5. 控制平面处理事件，更新状态，持久化事件日志
6. WebSocket广播更新到 `/topic/tasks/{taskId}`
7. 任务以 `TASK_DONE` 或 `TASK_FAILED` 结束
8. 用户通过短链接访问生成的Web应用

## 安全模型

### 认证与授权

- 控制平面认证模式：
  - `token` 模式：传统Token过滤器
  - `jwt` 模式：资源服务器 + 角色映射
- JWT模式同时支持传统 `X-Agent-Token` 适配器以保持Agent兼容性
- 项目级授权通过方法安全实现 (`@projectAuthz`)
- 任务/产物安全使用非枚举行为（未授权返回 `404`）

### 沙箱安全

- 可选mTLS强制执行，范围限定 `/api/v1/agent/**`
- Java Agent命令执行受策略链保护：
  - 特权升级检测 (`sudo`, `runas`, ...)
  - 敏感环境变量访问检测
  - 网络访问门控
  - 文件读写路径限制
  - 工作空间白名单强制执行
- 沙箱服务器仅限本地访问 (`127.0.0.1`)
- 高风险操作需要审批上下文绑定

## Python Agent 设计

### 核心组件

- `AgentRunner`: 注册、心跳、轮询循环
- `AgentOrchestrator`: 主编排器
  - `IntentAgent`: 意图分类（生成/测试/部署/分析）
  - `PlannerAgent`: 计划生成
  - `CoderAgent`: 代码生成/补丁发送
  - `DagScheduler`: 并行review + test
  - 可选Web产物打包/上传 (`export.zip`)

### Web生成流程

```
prompt → WebTemplateGenerator → LLM → JSON(files) → 验证 → 写入工作空间
```

- 支持多种主题: `clean`, `modern`, `dark`, `playful`, `enterprise`
- 自动检测并拒绝通用模板产物
- 支持火山引擎Ark、OpenAI、Claude等多种LLM后端

### 工具链

- `ExecTool`: 委托命令执行到Java沙箱 (`/sandbox/execute`)
- `RedisMemory`: 按项目/会话/工作空间键复用之前的测试/部署命令上下文

## 协议契约

`shared-protocol` 定义并验证事件和沙箱契约：

| 契约 | 说明 |
|------|------|
| `TaskEvent` + `EventType` | 任务事件类型定义 |
| `SandboxExecuteRequest/Response` | 沙箱执行请求/响应 |
| `ToolManifest` | 工具清单和权限封装 |
| `ArtifactMetadata/Manifest` | 产物元数据 |
| `ServiceRuntimeDescriptor` | 服务运行时描述符 |

这确保Java和Python组件在独立演进时保持一致性。

## 快速开始

### Docker部署（推荐）

启动完整技术栈（MySQL, Redis, control-plane, Java agent, Python agent）：

```bash
# 1. 复制环境变量配置
cp .env.example .env
# 编辑 .env 文件，填入实际配置值

# 2. 启动服务
docker compose --profile fullstack up -d --build
```

控制平面端点：

```
http://localhost:8058
```

停止服务：

```bash
docker compose --profile fullstack down
```

注意事项：

- `python-agent` 共享Java agent网络命名空间，沙箱调用使用 `127.0.0.1:18080`
- 可选产物托管链接设置：
  - `MVP_ARTIFACTS_HOSTING_PUBLIC_BASE_URL`
  - `MVP_ARTIFACTS_DOWNLOAD_SHARED_TOKEN`

### 本地开发

**前置条件**：JDK 17+（推荐JDK 21）

**启动步骤**：

1. 复制环境变量配置：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入实际配置值
   ```

2. 启动基础设施：
   ```bash
   docker compose up -d
   ```

3. 构建Java模块：
   ```bash
   mvn -DskipTests install
   ```

4. 启动控制平面：
   ```bash
   cd control-plane-spring && mvn spring-boot:run
   ```

5. 启动Java Agent：
   ```bash
   cd pc-agent-java && mvn exec:java -Dexec.mainClass=com.autocode.agent.AgentApplication
   ```

6. （可选）启动Python Agent：
   ```bash
   cd python-agent
   pip install -r requirements.txt
   python main.py
   ```

7. 运行冒烟测试：
   ```powershell
   ./scripts/smoke-test.ps1
   ```

### 移动端开发

参见 [mobile-app/MANUAL_E2E.md](mobile-app/MANUAL_E2E.md)

## 环境变量配置

### 控制平面 (control-plane-spring)

| 变量 | 说明 |
|------|------|
| `MVP_DB_URL` | MySQL数据库URL |
| `MVP_DB_USERNAME` / `MVP_DB_PASSWORD` | 数据库凭据 |
| `MVP_REDIS_HOST` / `MVP_REDIS_PORT` / `MVP_REDIS_PASSWORD` | Redis配置 |
| `MVP_AUTH_MODE` | 认证模式 (`jwt` 或 `token`) |
| `MVP_JWT_SECRET` | JWT密钥 |
| `MVP_MTLS_REQUIRED_FOR_AGENT` | Agent端mTLS要求 |

### Java Agent (pc-agent-java)

| 变量 | 说明 |
|------|------|
| `MVP_BASE_URL` | 控制平面URL |
| `MVP_NODE_ID` | 节点标识 |
| `MVP_AGENT_TOKEN` | Agent认证Token |
| `MVP_AGENT_PROFILE` | Agent配置文件 |
| `MVP_ALLOWED_COMMAND_PREFIXES` | 允许的命令前缀 |
| `MVP_ALLOWED_WORKSPACE_PREFIXES` | 允许的工作空间路径前缀 |
| `MVP_NETWORK_ALLOWED` | 是否允许网络访问 |
| `MVP_SANDBOX_SERVER_ENABLED` / `MVP_SANDBOX_PORT` | 沙箱服务器配置 |

### Python Agent

| 变量 | 说明 |
|------|------|
| `MVP_BASE_URL` | 控制平面URL |
| `MVP_NODE_ID` | 节点标识 |
| `MVP_AGENT_TOKEN` | Agent认证Token |
| `MVP_SANDBOX_BASE_URL` | Java沙箱URL |
| `MVP_MEMORY_BACKEND` | 内存后端 (`redis` 或 `memory`) |
| `MVP_REDIS_URL` | Redis URL |
| `LLM_CONFIG_PATH` | LLM配置文件路径 |
| `ARK_API_KEY` | 火山引擎Ark API密钥 |
| `LLM_BACKEND` / `LLM_MODEL` | LLM后端覆盖 |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 可选LLM API密钥 |

### Web模板生成

| 变量 | 说明 |
|------|------|
| `WEB_TEMPLATE_PROMPT_MODE` | 提示模式 (`direct` 或 `contract`) |

## API参考

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/tasks` | POST | 创建任务 |
| `/api/v1/tasks/{taskId}` | GET | 获取任务状态 |
| `/api/v1/artifacts/{artifactId}` | GET | 获取产物 |
| `/api/v1/artifacts/{artifactId}/download` | GET | 下载产物ZIP |
| `/api/v1/agent/tasks/next` | GET | Agent轮询下一个任务 |

### WebSocket主题

| 主题 | 说明 |
|------|------|
| `/topic/tasks/{taskId}` | 任务状态更新 |
| `/topic/projects/{projectId}` | 项目级事件 |

## 更多文档

- [后端架构详细设计](docs/backend-architecture-java-security-python-agent.md)
- [开发路线图](docs/roadmap.md)

## 技术栈

- **后端**: Spring Boot 3.x, MySQL 8.x, Redis 7.x
- **AI**: Python 3.11+, OpenAI API / 火山引擎Ark
- **安全**: JWT, mTLS, RBAC
- **移动端**: Kotlin, Android SDK
- **部署**: Docker, Docker Compose

## 贡献指南

欢迎贡献代码！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与项目开发。

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。
