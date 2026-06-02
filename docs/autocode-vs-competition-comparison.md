# AutoCode 项目 vs 赛题对比分析与开发规划

> 生成日期: 2026-05-13
> 项目: AutoCode (D:\Develop\Project\AutoCode)
> 赛题: AgentHub 多Agent协作平台 | 超级个体 端到端全栈交付

---

## 一、项目现状概述

### 1.1 系统架构

AutoCode 是一个 AI 驱动的多 Agent 代码生成平台，采用微服务架构：

```
┌─────────────────────────────────────────────────────────────┐
│                    Android Client (Kotlin)                    │
│              mobile-app/ (Jetpack Compose, Material3)        │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + WebSocket/STOMP
┌──────────────────────────▼──────────────────────────────────┐
│              Gateway (Spring Cloud Gateway :8080)            │
│                   gateway-service/                           │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │
┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
│ Control     │ │ Artifact  │ │ Approval  │ │ Event     │
│ Plane       │ │ Service   │ │ Service   │ │ Service   │
│ (Spring Boot│ │           │ │           │ │           │
│  :8070)     │ │           │ │           │ │           │
└──────┬──────┘ └───────────┘ └───────────┘ └───────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                  Python Agent (Python 3.11)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────┐│
│  │ Intent   │→│ Planner  │→│ Coder    │→│Reviewer│→│Tester││
│  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent  │ │Agent ││
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ └──────┘│
│  ┌──────────────────────────────────────────────────────┐   │
│  │           AgentOrchestrator (DAG + LangGraph)        │   │
│  └──────────────────────────────────────────────────────┘   │
└──────┬──────────────────────────────────────────────────────┘
       │ HTTP
┌──────▼──────┐
│ Java Sandbox│   pc-agent-java/ (127.0.0.1:18080)
│ (命令执行)   │   安全策略链 + 工具注册
└─────────────┘
```

### 1.2 技术栈

| 层级 | 技术 | 文件位置 |
|------|------|---------|
| 后端服务 | Java 17+ / Spring Boot 3.3.5 | `control-plane-spring/`, `gateway-service/` 等 |
| AI Agent | Python 3.11 / LangGraph | `python-agent/` |
| 数据库 | MySQL 8.4 + Flyway 迁移 | `control-plane-spring/src/main/resources/db/migration/` |
| 缓存/队列 | Redis 7.4 | 任务队列、分布式锁、内存、去重 |
| 协议层 | 共享 DTO + JSON Schema 校验 | `shared-protocol/` |
| 客户端 | Android Kotlin / Jetpack Compose | `mobile-app/` |
| 部署 | Docker Compose + GitHub Actions CI | `docker-compose.yml`, `.github/` |
| 监控 | Prometheus + Grafana + Alertmanager | `ops/observability/` |

### 1.3 核心能力清单

#### 已有能力（经过代码验证）

| 能力 | 实现文件 | 具体描述 |
|------|---------|---------|
| **5-Agent 流水线** | `python-agent/orchestrator/agent_orchestrator.py` L67 | Intent → Planner → Coder → Reviewer → Tester 完整链路 |
| **DAG 并行执行** | `python-agent/orchestrator/dag_scheduler.py` | Reviewer + Tester 并行执行，ThreadPoolExecutor(max=4) |
| **LangGraph 双引擎** | `python-agent/orchestrator/langgraph_runtime.py` | legacy DAG + langgraph StateGraph，环境变量切换 |
| **18 种事件协议** | `shared-protocol/.../EventType.java` | TASK_CREATED 到 HEARTBEAT，完整事件类型 |
| **WebSocket 实时推送** | `control-plane-spring/.../WebSocketConfig.java` | STOMP /ws 端点，/topic/tasks/{taskId} 订阅 |
| **审批机制** | `control-plane-spring/.../TaskService.java` L605-631 | APPROVAL_REQUIRED → ApprovalEntity → 轮询决策 → 上下文漂移检测 |
| **Fix Loop** | `python-agent/generators/fix_loop.py` | 错误分类(语法/结构/依赖/运行时) → 规则修复 + LLM 修复，最多 3 轮 |
| **Validation Gate** | `python-agent/generators/validation_gate.py` | Python AST 语法检查、HTML 标签匹配、CSS 大括号平衡、依赖格式验证 |
| **插件系统** | `python-agent/plugins/` | PluginRegistry + CircuitBreaker + Manifest 权限控制 |
| **代码生成** | `python-agent/generators/` | Web(HTML/CSS/JS)、Backend(Flask+SQLite)、Fullstack 模板 |
| **LLM 多后端** | `python-agent/llm/llm_client.py` | OpenAI 兼容 + Anthropic Claude，Profile 配置，LRU+TTL 缓存 |
| **RBAC + JWT** | `control-plane-spring/.../JwtSecurityConfig.java` | admin/operator/owner/viewer 四角色，JWT 认证 |
| **审计日志** | `control-plane-spring/.../AuditService.java` | Hash 链式审计，防篡改 |
| **分布式锁** | `python-agent/orchestrator/distributed_lock.py` | Redis 分布式锁，防止重复执行 |
| **可观测性** | `python-agent/utils/observability.py` + Prometheus | Task span 追踪、指标采集、缓存命中率 |

---

## 二、Conduit (RealWorld) 仓库结构分析

### 2.1 什么是 Conduit

Conduit 是 [gothinkster/realworld](https://github.com/gothinkster/realworld) 的全栈实现，一个 **Medium.com 克隆**，是业界最流行的全栈 Demo 项目之一。赛题要求在此仓库上实现端到端交付。

### 2.2 典型 Monorepo 结构

```
conduit/
├── packages/
│   ├── client/                     # 前端 SPA
│   │   ├── src/
│   │   │   ├── components/         # ArticleCard, CommentForm, Navbar, TagList...
│   │   │   ├── pages/              # Home, Article, Editor, Profile, Settings, Auth
│   │   │   ├── services/           # API 调用层 (agent.ts / api.ts)
│   │   │   ├── store/              # 状态管理 (Redux/Zustand/Pinia)
│   │   │   └── types/              # TypeScript 类型定义
│   │   ├── package.json
│   │   └── vite.config.ts
│   ├── server/                     # 后端 API
│   │   ├── src/
│   │   │   ├── routes/             # articles, users, profiles, tags, comments
│   │   │   ├── models/             # User, Article, Comment, Tag 数据模型
│   │   │   ├── middleware/         # auth (JWT), error-handler, validator
│   │   │   └── config/             # db, env, passport
│   │   ├── tests/                  # API 测试
│   │   └── package.json
│   └── shared/                     # 共享类型/工具
├── package.json                    # workspaces 根配置
├── turbo.json / nx.json            # 构建编排
└── README.md
```

### 2.3 六大业务领域

| 领域 | 功能 | 涉及文件 |
|------|------|---------|
| **Auth** | 注册、登录、JWT 鉴权、获取当前用户 | `server/routes/users`, `server/middleware/auth`, `client/services/auth` |
| **Articles** | 文章 CRUD、分页、按标签/作者筛选、Feed 流 | `server/routes/articles`, `client/pages/Home`, `client/components/ArticleList` |
| **Comments** | 评论 CRUD | `server/routes/articles/:slug/comments`, `client/components/CommentCard` |
| **Favorites** | 收藏/取消收藏 | `server/routes/articles/:slug/favorite`, `client/components/FavoriteButton` |
| **Profiles** | 用户主页、关注/取关 | `server/routes/profiles`, `client/pages/Profile` |
| **Tags** | 标签列表、按标签过滤 | `server/routes/tags`, `client/components/TagList` |

### 2.4 API 约定

```
POST   /api/users/login           → { user: { email, token, username, bio, image } }
POST   /api/users                 → 注册
GET    /api/articles?limit=20&offset=0&tag=react  → 文章列表
POST   /api/articles              → { article: { title, description, body, tagList } }
PUT    /api/articles/:slug        → 更新
DELETE /api/articles/:slug        → 删除
POST   /api/articles/:slug/comments     → { comment: { body } }
POST   /api/articles/:slug/favorite     → 收藏
GET    /api/profiles/:username    → 用户资料
POST   /api/profiles/:username/follow   → 关注
GET    /api/tags                  → 所有标签
```

### 2.5 对 AutoCode 的能力要求

要在 Conduit 上实现端到端交付，AutoCode 需要：

1. **克隆真实仓库** — 不是从零生成，而是 `git clone` 一个已有项目
2. **理解代码结构** — AST 解析、模块依赖图、框架识别
3. **增量代码修改** — 在已有 React 组件 / Express 路由上做定向修改
4. **多框架支持** — React/Vue/Angular + Express/Nest/Fastify（不只是 Flask）
5. **测试生成** — 为已有代码生成 Jest/Mocha/pytest 测试用例
6. **Git 操作** — branch、commit、push、PR 全流程
7. **多轮对话** — PM 追问、澄清、修订方案
8. **人工介入** — 每个阶段可暂停/审批/修订

---

## 三、赛题 1 对比: AgentHub 多 Agent 协作平台

### 3.1 逐项匹配度

| 需求项 | AutoCode 现状 | 匹配度 | 关键缺失 |
|--------|-------------|--------|---------|
| **IM 聊天式交互界面** | 无 Web UI，仅有 Android 原生 App (`mobile-app/`) 和 REST API | **10%** | 整个 Web 聊天前端：React/Vue 聊天组件、WebSocket 消息流、Markdown 渲染、代码高亮 |
| **统一适配器层 (Claude Code, Codex)** | 仅自有 Python Agent，`claudecode-runner/` 目录为空 | **5%** | Adapter SPI 接口设计、Claude Code SDK 适配器、OpenAI Codex 适配器、协议转换层 |
| **单聊 / 多会话并行** | 单 task 单 session，`AgentRunner` 轮询获取下一个 task (`python-agent/runner.py`) | **10%** | Session 管理器、并行会话调度、会话上下文隔离、会话历史持久化 |
| **@ 指令群聊协作** | 无群组概念，无命令路由系统 | **0%** | @命令解析器（@code @test @deploy @review）、Agent 路由表、群组消息分发 |
| **Orchestrator 任务拆解** | `PlannerAgent` 生成线性步骤列表 (`planner_agent.py` L82-96)，`DagScheduler` 支持 DAG 并行 | **40%** | 任务树（非线性分解）、子任务分配到不同 Agent、跨 Agent 协调、进度聚合 |
| **Code Diff 展示** | CoderAgent 生成 unified diff 并发送 `FILE_PATCH_PREVIEW` 事件 (`coder_agent.py` L101-124) | **60%** | Web 端 diff 渲染器（Monaco/CodeMirror）、side-by-side 对比、交互式 accept/reject |
| **网页预览** | 产物打包为 export.zip，`HostedArtifactSiteService` 提供静态托管 | **50%** | iframe 沙箱预览、实时热更新、交互式编辑 |
| **一键部署** | `ExecTool` 委托 Java sandbox 执行命令 (`exec_tool.py` L55-92) | **45%** | Web 端部署按钮、部署状态追踪、环境管理、回滚 UI |
| **TRAE 协作** | 无任何 TRAE 集成 | **0%** | TRAE API 适配器、IDE 集成、实时同步 |
| **Prompt 工程** | System prompt 硬编码在各 Agent 中 (`intent_agent.py` L57-68, `planner_agent.py` L83-96) | **15%** | Prompt 模板管理、版本控制、A/B 测试、可视化编辑器 |
| **架构创新** | DAG 并行 + LangGraph 双引擎 + Plugin 系统 + Circuit Breaker + Outbox 模式 | **55%** | 适配器 SPI 设计、协议标准化文档、Agent 编排可视化 |

### 3.2 赛题 1 总体匹配度: ~25%

### 3.3 赛题 1 核心差距

```
差距热力图 (■ 完全缺失  □ 严重不足  ▒ 有基础但不足  ░ 基本满足)

Web IM 界面        ■■■■■■■■■■  10%
Agent 适配器层     ■■■■■■■■■■   5%
@ 指令群聊        ■■■■■■■■■■   0%
TRAE 协作         ■■■■■■■■■■   0%
多会话并行        ■■■■■■■■■■  10%
Prompt 管理       ■■■■■■■■□□  15%
一键部署          ▒▒▒▒▒▒▒▒░░  45%
网页预览          ▒▒▒▒▒▒▒▒░░  50%
任务编排          ▒▒▒▒▒▒░░░░  40%
架构创新          ▒▒▒▒▒░░░░░  55%
Code Diff         ▒▒▒▒░░░░░░  60%
```

---

## 四、赛题 2 对比: 超级个体 端到端全栈交付

### 4.1 逐项匹配度

| 需求项 | AutoCode 现状 | 匹配度 | 关键缺失 |
|--------|-------------|--------|---------|
| **克隆并理解现有仓库** | `SearchTool` 是朴素文本 grep (`search_tool.py` L6-37)，无 AST、无向量存储 | **5%** | Git clone、AST 解析 (tree-sitter)、代码索引、语义搜索、仓库结构分析 |
| **需求澄清（多轮对话）** | `IntentAgent` 单次分类 4 种意图 (`intent_agent.py` L11)，无多轮对话 | **5%** | DialogueManager、澄清问题生成、需求文档生成器、对话状态机 |
| **方案分解** | `PlannerAgent` 生成线性步骤 (`planner_agent.py`)，不理解现有代码结构 | **20%** | 基于仓库上下文的方案设计、模块边界识别、依赖分析 |
| **模块定位** | `_choose_target_file` 按 "readme" 关键词或字母序选文件 (`coder_agent.py` L379-401) | **5%** | AST 级代码理解、模块图谱、变更影响分析、智能文件定位 |
| **代码生成（增量修改）** | `BackendGenerator` 生成固定 Flask CRUD (`backend_generator.py` L13-21)，LLM 编辑仅在 framework 关键词时触发 (`coder_agent.py` L459-478) | **10%** | 增量 patch 生成、多文件协同编辑、React/Express 框架适配、代码风格保持 |
| **自动化测试生成** | `TesterAgent` 仅执行已有命令，回退到 `echo test_from_python_agent` (`tester_agent.py` L251-258) | **5%** | 测试用例生成、Jest/Mocha/pytest 适配、覆盖率分析 |
| **代码部署** | `ExecTool` 委托 sandbox 执行，回退到 `echo deploy_from_python_agent` (`agent_orchestrator.py` L998-1014) | **15%** | 容器化部署模板、环境管理、健康检查、回滚 |
| **全流程人工介入** | 仅 sandbox 命令审批 (`ApprovalEntity`, `approval_workflow.py`) | **15%** | 需求确认门、方案审批门、代码审查门、测试确认门 |
| **知识写回** | `RedisMemory` 存储 task metadata (intent/planName/status)，50 条/项目 (`redis_memory.py` L73-93) | **10%** | 代码知识图谱、学习经验库、向量嵌入、跨迭代知识复用 |
| **Conduit 仓库适配** | 仅支持从 scratch 生成，不支持 React/Express | **5%** | React 组件理解、Express 路由理解、Monorepo 结构理解 |
| **3 周交付可行性** | 已有 CI/CD、Docker Compose、Prometheus/Grafana 监控 | **30%** | 端到端 Demo pipeline、staging 环境 |

### 4.2 赛题 2 总体匹配度: ~12%

### 4.3 赛题 2 核心差距

```
差距热力图 (■ 完全缺失  □ 严重不足  ▒ 有基础但不足  ░ 基本满足)

仓库理解          ■■■■■■■■■■   5%
模块定位          ■■■■■■■■■■   5%
测试生成          ■■■■■■■■■■   5%
Conduit 适配      ■■■■■■■■■■   5%
需求澄清          ■■■■■■■■■■   5%
代码生成(增量)    ■■■■■■■■□□  10%
知识写回          ■■■■■■■■□□  10%
人工介入(全阶段)  ■■■■■■■□□□  15%
部署              ■■■■■■■□□□  15%
方案分解          ▒▒▒▒▒▒▒▒░░  20%
3周交付           ▒▒▒▒▒▒▒░░░  30%
```

---

## 五、核心差异总结

### 5.1 范式差异（根本性）

| 维度 | AutoCode 现状 | 两个赛题的共同需求 |
|------|-------------|-----------------|
| **代码生成模式** | 从零生成 (template-based from-scratch) | 在现有仓库上增量修改 (incremental modification) |
| **输入模式** | 单次 prompt → 单次输出 (one-shot) | 多轮对话 → 持续迭代 (multi-turn dialogue) |
| **代码理解** | 无理解（SearchTool 做文本 grep，CoderAgent 按文件名选文件） | 深度理解（AST、语义索引、依赖图、调用图） |
| **目标框架** | Flask+SQLite CRUD、HTML/CSS/JS 静态页 | React/Vue/Angular SPA、Express/Nest API、全栈 monorepo |
| **测试能力** | 执行已有命令（fallback: `echo test_from_python_agent`） | 生成测试用例、分析覆盖率、迭代修复 |
| **版本控制** | 只读 `git diff --numstat` | clone/branch/commit/push/PR 完整 Git 操作 |
| **人工介入** | 仅命令执行审批 (APPROVAL_REQUIRED) | 全阶段人工门控（需求/方案/代码/测试/部署） |
| **知识持久化** | Redis task metadata（50 条/项目） | 代码知识图谱、向量嵌入、跨迭代学习 |

### 5.2 两个赛题之间的差异

| 维度 | 赛题 1: AgentHub | 赛题 2: 超级个体 |
|------|-----------------|-----------------|
| **核心挑战** | 构建 IM 交互体验 + 多 Agent 适配 | 构建代码理解 + 增量修改 + 全流程人工介入 |
| **前端工作量** | 极大（从零建 Web 聊天界面） | 小（可复用现有 Android App 或 API 调用） |
| **后端改造量** | 中（新增适配器层、会话管理） | 大（重写 CoderAgent、新增索引/对话/知识模块） |
| **创新点** | IM 交互 + @群聊 + Agent 适配器 | 全流程人工介入 + 知识回写 + Conduit 仓库实战 |
| **Demo 难度** | 中（UI 展示效果直观） | 高（需要端到端跑通完整链路） |
| **已有优势利用** | 编排引擎需包装成 Agent 适配器 | 编排引擎直接复用，聚焦业务层改造 |
| **3 周可行性** | 紧张（Web 前端工作量大） | 可行（后端已有，聚焦改造） |

---

## 六、核心相同点（可复用资产）

以下资产在两个赛题中均可直接复用或小幅扩展：

| 资产 | 文件位置 | 复用场景 |
|------|---------|---------|
| **Event Protocol (18 种事件)** | `shared-protocol/.../EventType.java` | Agent 间通信协议基础，可扩展新事件类型 |
| **Approval 机制** | `control-plane-spring/.../TaskService.java` L605-631 | 赛题 2 的 Human-in-the-Loop 可直接扩展 |
| **DAG Scheduler** | `python-agent/orchestrator/dag_scheduler.py` | 任务分解后的并行执行 |
| **Plugin 系统** | `python-agent/plugins/` | 两个赛题的扩展点均可通过 plugin 实现 |
| **LLM Client (多后端)** | `python-agent/llm/llm_client.py` | OpenAI/Claude/Ark 多后端 + 缓存 + 重试 |
| **Fix Loop** | `python-agent/generators/fix_loop.py` | 代码生成后的自动修复循环 |
| **Validation Gate** | `python-agent/generators/validation_gate.py` | 代码质量保障，可扩展更多语言 |
| **基础设施** | `docker-compose.yml`, `ops/` | Docker Compose + Prometheus + Grafana + Redis + MySQL |
| **Circuit Breaker** | `python-agent/utils/circuit_breaker.py` | Agent 调用保护 |
| **Outbox 模式** | `python-agent/outbox/` | 事件可靠投递 |
| **可观测性** | `python-agent/utils/observability.py` | Tracing + Metrics |

---

## 七、未来开发规划

### 7.1 Phase 1: 基础能力补齐（两个赛题共同需要，1-2 周）

| 优先级 | 任务 | 新建/修改文件 | 工作量 | 说明 |
|--------|------|-------------|--------|------|
| **P0** | Git 工具封装 | `python-agent/tools/git_tool.py` (新建) | 2-3 天 | clone / branch / commit / diff / checkout，基于 subprocess 调用 git CLI |
| **P0** | 代码索引 | `python-agent/indexing/` (新建) | 3-5 天 | repo_scanner (目录扫描+框架识别) + file_indexer (函数/类/导入提取) + context_builder (LLM 上下文注入) |
| **P0** | 多轮对话 | `python-agent/dialogue/` (新建) | 3-5 天 | DialogueManager (对话状态机) + 澄清问题生成 + PRD 生成器 + CLARIFICATION_REQUIRED 事件 |
| **P1** | 增量代码修改 | `python-agent/agents/coder_agent.py` (重构) | 5-7 天 | 基于模块定位选文件 + LLM 上下文注入仓库结构 + 多文件协同编辑 + unified diff 输出 |
| **P1** | 测试生成 | `python-agent/generators/test_generator.py` (新建) | 3-5 天 | 基于代码结构生成 Jest/pytest 测试用例，集成到 TesterAgent |
| **P1** | 全流程人工介入 | `python-agent/plugins/approval_workflow.py` (扩展) + `shared-protocol/.../EventType.java` (扩展) | 3-4 天 | 新增 PLAN_REVIEW_REQUIRED、CODE_REVIEW_REQUIRED、TEST_REVIEW_REQUIRED 事件，在每个 Agent 阶段前插入审批门控 |

### 7.2 Phase 2a: 赛题 1 专项 — AgentHub（2-3 周）

| 优先级 | 任务 | 工作量 | 说明 |
|--------|------|--------|------|
| **P0** | Web 聊天前端 | 5-7 天 | React 18 + Vite + TailwindCSS，WebSocket/STOMP 对接，消息气泡、Markdown 渲染、代码高亮 |
| **P0** | Agent 适配器层 | 5-7 天 | AgentAdapter SPI 接口 + ClaudeCodeAdapter (Anthropic SDK) + CodexAdapter (OpenAI SDK) + 协议转换 |
| **P1** | 多 session 并行 | 3-5 天 | SessionManager + 并行 workspace 隔离 + 会话列表 UI |
| **P1** | @ 指令系统 | 3-4 天 | @命令解析器 + Agent 路由表 + 群组消息分发 |
| **P2** | Diff 组件 + 预览 | 4-5 天 | Monaco Editor diff viewer + iframe 沙箱预览 |
| **P2** | Prompt 管理 | 3-4 天 | 模板库 + 版本历史 + 可视化编辑器 |

### 7.3 Phase 2b: 赛题 2 专项 — 超级个体（2-3 周）

| 优先级 | 任务 | 工作量 | 说明 |
|--------|------|--------|------|
| **P0** | 需求澄清对话流 | 4-5 天 | DialogueManager 集成到 Orchestrator，模糊度检测 → 追问 → PRD → 用户确认 |
| **P0** | Conduit 仓库适配 | 5-7 天 | React 组件模板 + Express 路由模板 + monorepo 构建编排器 + 框架识别器 |
| **P1** | 知识写回 | 4-5 天 | KnowledgeStore (Redis Hash) + 代码模式库 + 迭代经验库 + 向量检索 (ChromaDB) |
| **P1** | 一键部署 | 3-4 天 | 容器化部署模板 + 环境管理 + 健康检查 + 回滚 |
| **P2** | 端到端 Demo | 5-7 天 | Conduit 仓库完整链路：需求 → 方案 → 代码 → 测试 → 部署 |

### 7.4 关键文件修改清单

| 文件 | 修改内容 | 适用赛题 |
|------|---------|---------|
| `python-agent/agents/coder_agent.py` | 重构 `_choose_target_file` (L379) 和 `_propose_content` (L403)，支持基于索引的增量修改 | 两个 |
| `python-agent/orchestrator/agent_orchestr.py` | 扩展 `_handle_task_locked` (L103)，新增对话、人工介入、知识回写阶段 | 两个 |
| `python-agent/tools/search_tool.py` | 替换为 AST-based CodeIndexTool，或并行保留两者 | 两个 |
| `python-agent/memory/redis_memory.py` | 扩展支持代码知识存储、向量嵌入 | 赛题 2 |
| `shared-protocol/.../EventType.java` | 新增 DIALOGUE_TURN、PLAN_REVIEW_REQUIRED、CODE_REVIEW_REQUIRED、KNOWLEDGE_WRITEBACK 等事件 | 两个 |
| `python-agent/plugins/approval_workflow.py` | 扩展支持全阶段审批门控 | 两个 |
| `python-agent/agents/tester_agent.py` | 集成 TestGenerator，支持自动生成测试用例 | 赛题 2 |

---

## 八、技术选型建议

| 能力域 | 推荐技术 | 理由 |
|--------|---------|------|
| **代码索引/AST** | tree-sitter + tree-sitter-{python,java,typescript,javascript} | 多语言 AST 解析，增量解析性能好，社区活跃 |
| **向量存储** | ChromaDB 或 Qdrant | 轻量级，可嵌入 Python 进程，支持语义搜索 |
| **代码生成 LLM** | Claude Sonnet 4 / GPT-4.1 + prompt caching | 代码理解能力强，`llm_client.py` 已有 cache 机制 |
| **Web 前端 (赛题 1)** | React 18 + Vite + TailwindCSS + shadcn/ui | 与 Conduit 前端技术栈一致，组件生态丰富 |
| **聊天组件** | 自定义 React 组件 + WebSocket (STOMP over SockJS) | 控制平面已有 `WebSocketConfig.java` 和 STOMP 支持 |
| **Diff 渲染** | Monaco Editor diff viewer 或 react-diff-viewer | VSCode 级别的 diff 体验，语法高亮 |
| **Web Preview** | iframe sandbox + Vite HMR | 实时预览，安全隔离 |
| **Git 操作** | GitPython (Python) 或 subprocess + git CLI | 原生集成，API 友好 |
| **Agent 适配器** | Anthropic SDK (Claude Code) + OpenAI SDK (Codex) | 官方 SDK，协议对齐 |
| **知识图谱** | NetworkX (内存原型) → Neo4j (持久化) | 先轻量验证，再持久化 |
| **测试生成** | LLM + AST 分析 + 模板匹配 | 结合 AST 理解代码结构，LLM 生成测试用例 |
| **Monorepo 构建** | turbo (推荐) 或 nx | Conduit 生态标准 |

---

## 九、风险评估

### 9.1 共同风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 现有代码大规模重构引入回归 | 高 | 新能力作为 plugin/extension 接入，保持现有 pipeline 可用 |
| LLM 调用成本和延迟 | 中 | 利用 `llm_client.py` 已有 LRU+TTL cache，控制 token 用量 |
| 测试覆盖不足 | 中 | 现有 130+ 测试文件，新增功能配套测试 |

### 9.2 赛题 1 专项风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Web 前端开发周期长 | 高 | 优先核心聊天 + diff + preview，其他 MVP 简化 |
| Agent 适配器层协议不一致 | 高 | 先实现 Claude Code 适配器验证 SPI，再扩展 |
| TRAE 接口文档不充分 | 中 | 预留 adapter 接口，TRAE 集成可后补 |

### 9.3 赛题 2 专项风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 代码索引/AST 是全新模块 | 高 | 先支持 TypeScript/JavaScript (Conduit 主语言)，渐进扩展 |
| Conduit 仓库结构复杂 | 高 | 先选择一个实现 (如 react-redux-realworld-example-app) 降低复杂度 |
| 增量代码修改质量不稳定 | 高 | 强化 fix loop + validation gate + 人工审查门控 |
| 3 周时间极其紧张 | 高 | 聚焦核心 E2E 流程，部署简化 |
| 多轮对话上下文管理复杂 | 中 | 限制对话轮次 (最多 10 轮)，structured output 减少歧义 |

---

## 十、结论与建议

### 10.1 赛题选择建议

| 维度 | 赛题 1: AgentHub | 赛题 2: 超级个体 |
|------|-----------------|-----------------|
| **匹配度** | ~25% | **~12%** |
| **需新建工作量** | 极大（Web 前端 + 适配器层） | 中（仓库感知 + 对话 + 知识） |
| **核心优势发挥** | 编排引擎需包装成适配器 | **编排引擎直接复用** |
| **创新点** | IM 交互 + @群聊 | **全流程人工介入 + 知识回写** |
| **3 周可行性** | 紧张 | **可行** |

**建议选择赛题 2（超级个体）**：

1. 匹配度更高 — 项目后端编排能力可直接复用，差距集中在前端改造和对话能力
2. 3 周可行 — 不需要从零建 Web 前端，聚焦后端能力补齐
3. 创新空间大 — 全流程人工介入 + 知识回写是独特卖点
4. 展示效果好 — 在 Conduit 仓库上跑通完整链路，Demo 说服力强

### 10.2 关键成功因素

1. **先跑通最小链路**: 需求 → 方案 → 代码 → 测试，每个阶段先做 MVP
2. **善用 LLM 能力**: 不要试图用规则覆盖所有场景，LLM 处理边界情况
3. **渐进式改造**: 保持现有 pipeline 可用，新能力作为 plugin 接入
4. **聚焦 Conduit**: 选定一个 Conduit 实现，深耕而非泛化
