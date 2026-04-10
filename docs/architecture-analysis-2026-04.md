# AutoCode 项目架构分析报告

> 生成时间：2026-04-09  
> 基线版本：origin/master（PR #77）

---

## 一、系统架构总览

AutoCode 是一个**企业级 AI Agent 代码生成平台**，目标是通过移动端自然语言输入，驱动 AI Agent 自动完成代码修改、测试、审批、产物交付的完整闭环。

### 1.1 组件全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        Mobile App (Android)                      │
│  语音/文本输入 → 任务创建 → 实时事件流 → 审批交互 → 产物下载      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP + WebSocket (STOMP)
┌────────────────────────────▼────────────────────────────────────┐
│                   Control Plane (Spring Boot)                    │
│  任务调度 | 事件落库 | WebSocket广播 | 审批流 | 审计 | 产物管理   │
│  MySQL (JPA+Flyway) | Redis (队列/缓存) | STOMP WebSocket        │
└──────────┬──────────────────────────────────────┬───────────────┘
           │ HTTP轮询 (mTLS可选)                   │ HTTP轮询
┌──────────▼──────────┐                ┌──────────▼──────────────┐
│   PC Agent (Java)   │                │  Python Agent           │
│  注册/心跳/轮询      │                │  意图识别/计划/编码/审查  │
│  命令执行沙箱        │                │  DAG调度 | Redis内存     │
│  工作区白名单        │                │  LLM客户端(待实现)       │
│  审批等待            │                │  Fix Loop(待实现)        │
└─────────────────────┘                └─────────────────────────┘
           │
┌──────────▼──────────┐
│  Sandbox HTTP Server│
│  (Java本地沙箱)      │
└─────────────────────┘
```

### 1.2 核心数据流

```
用户输入 → 创建任务(幂等) → 入队 → Agent轮询领取 → 执行
    ↓                                      ↓
  WebSocket                          上报事件(seq)
    ↓                                      ↓
  移动端实时展示 ← 广播 ← 事件落库 ← 控制面摄取
                                           ↓
                                    高风险 → 审批门禁
                                           ↓
                                    产物上传 → ARTIFACT_READY
```

### 1.3 共享协议层（shared-protocol）

所有组件通过 `shared-protocol` 模块共享 DTO：
- `TaskSummary` / `TaskEvent` / `EventType` / `TaskStatus`
- `ApprovalDecision` / `CreateTaskRequest`
- 产物相关：`ArtifactManifest` / `ArtifactMetadata`
- 部署相关：`DeployPayload`

---

## 二、各组件实现状态

### 2.1 Control Plane（Spring Boot）✅ 基本完整

**已实现：**
- 任务 CRUD（创建/查询/取消/审批）+ 幂等键（SHA-256 确定性 taskId）
- 事件摄取：去重、seq 分配、状态机驱动、落库、WebSocket 广播
- 队列分发：支持 Redis/InMem，DB 模式（`mvp.scheduler.mode=db`）
- 审批强绑定：记录 command/cwd/inputsHash，执行前校验防漂移
- 审计日志（AuditService）
- 租约管理：lease 过期自动回收重入队
- Profile 路由（coder/reviewer/tester）
- Lane 串行（sessionKey 隔离）
- 基础 RBAC（JWT 模式）
- OpenAPI 文档
- 可观测性指标（Micrometer）

**待完善：**
- 产物存储（当前仅本地文件，缺 MinIO/S3 适配）
- 完整 RBAC（project-scoped 资源级授权）
- 审计不可篡改（hash chain + WORM 归档）

### 2.2 PC Agent（Java）✅ 基本完整

**已实现：**
- 注册/心跳/轮询领取任务主循环
- 命令执行沙箱（SandboxHttpServer）
- 工作区白名单（WorkspaceAllowlistPolicy）
- 命令安全策略（CommandSafetyPolicy）
- 审批等待（APPROVAL_REQUIRED 事件 + 轮询决策）
- 事件回传（结构化 TaskEvent）
- 热重载配置（MVP_AGENT_CONFIG_PATH）
- mTLS 客户端证书支持

**待完善：**
- 真实 Generator Engine 集成（claudecode 包装）
- 自动更新/回滚机制
- 服务化运行（Windows Service）

### 2.3 Python Agent ⚠️ 骨架完整，核心能力缺失

**已实现（骨架）：**
- 六类 Agent 框架（Intent/Planner/Coder/Reviewer/Tester + Orchestrator）
- DAG 调度器（并行执行，依赖拓扑排序）
- Redis 内存管理（跨任务上下文，本地降级）
- Control Plane 客户端（HTTP 轮询）
- ExecTool（调用 Java 沙箱）
- FileTool / SearchTool

**关键缺陷（核心能力缺失）：**
- `llm_client.py`：**文件为空**，无任何 LLM 调用实现
- `utils/diff_utils.py`：**不存在**，无 diff 生成能力
- `IntentAgent`：关键词匹配，非 LLM 驱动
- `PlannerAgent`：固定模板，非动态计划
- `CoderAgent`：仅追加注释（`# coder-agent-note: ...`），非真实代码改写
- `ReviewerAgent`：`REVIEW_BLOCKER` 关键词扫描，非 diff 审查
- Fix Loop：未实现（测试失败后无自动修复）

### 2.4 Mobile App（Android/Kotlin）⚠️ 基础功能完整，高级功能缺失

**已实现：**
- 登录/会话管理（DataStore 持久化）
- 任务创建（HTTP + 本地模拟双模式）
- 任务列表/详情
- HTTP 轮询进度
- WebSocket STOMP 实时事件流（含断线重连、增量补流）
- 审批交互（submitApproval）
- 产物列表/预览/下载
- 发布历史记录

**待完善：**
- 语音输入（SpeechRecognizer 集成）
- Agent 工作过程可视化（markdown diff 渲染）
- 代码变更 diff 展示（FILE_PATCH_PREVIEW 渲染）
- 推送通知（任务完成/审批请求）
- 离线模式完善

---

## 三、距离最终产品的缺陷清单

### 3.1 P0 级缺陷（阻塞核心功能）

| # | 缺陷 | 影响 | 所在模块 |
|---|------|------|---------|
| D-01 | `llm_client.py` 文件为空，无 LLM 调用 | Python Agent 无法真实理解意图、生成计划、修改代码 | python-agent/llm |
| D-02 | `diff_utils.py` 不存在 | 无法生成 unified diff，CoderAgent/ReviewerAgent 无法输出真实变更 | python-agent/utils |
| D-03 | CoderAgent 仅追加注释，非真实代码改写 | 产物无实际价值，整个代码生成链路失效 | python-agent/agents |
| D-04 | IntentAgent 关键词匹配，无 LLM 意图识别 | 复杂自然语言指令无法正确解析 | python-agent/agents |
| D-05 | PlannerAgent 固定模板，无动态计划 | 无法根据任务内容生成针对性执行步骤 | python-agent/agents |
| D-06 | ReviewerAgent 无 diff 审查 | 代码质量无法评估，审批流缺乏依据 | python-agent/agents |
| D-07 | Fix Loop 未实现 | 测试失败后无自动修复，需人工干预 | python-agent/orchestrator |
| D-08 | 产物存储无持久化后端 | 产物仅存本地，无法跨节点访问，生产不可用 | control-plane-spring |

### 3.2 P1 级缺陷（影响生产可用性）

| # | 缺陷 | 影响 | 所在模块 |
|---|------|------|---------|
| D-09 | 长生命周期共享 token，无刷新机制 | token 泄露后无法快速吊销，安全风险高 | control-plane-spring |
| D-10 | 缺少 project-scoped 资源级授权 | 任意用户可访问其他项目的任务和产物 | control-plane-spring |
| D-11 | 审计日志可篡改（无 hash chain） | 不满足企业合规要求 | control-plane-spring |
| D-12 | PC Agent 无真实 Generator Engine | 当前仅执行 mock 命令，无实际代码生成能力 | pc-agent-java |
| D-13 | 移动端无语音输入 | 核心交互方式缺失，降级为纯文本 | mobile-app |
| D-14 | 移动端无 diff 渲染 | FILE_PATCH_PREVIEW 事件无法可视化展示 | mobile-app |
| D-15 | Python Agent 无 requirements.txt/pyproject.toml | 依赖管理缺失，部署困难 | python-agent |
| D-16 | 无端到端集成测试 | 各组件单独测试，跨组件链路未验证 | 全局 |

### 3.3 P2 级缺陷（影响规模化）

| # | 缺陷 | 影响 | 所在模块 |
|---|------|------|---------|
| D-17 | 无 MQ 适配（Rabbit/Kafka） | 高并发场景下 Redis 队列成为瓶颈 | control-plane-spring |
| D-18 | PC Agent 无自动更新机制 | 版本升级需手动操作，运维成本高 | pc-agent-java |
| D-19 | 无分布式追踪（traceId 贯穿） | 跨组件问题排查困难 | 全局 |
| D-20 | 移动端无推送通知 | 用户需主动刷新才能感知任务状态变化 | mobile-app |
| D-21 | 无多租户隔离 | 企业级部署时数据隔离不足 | control-plane-spring |

---

## 四、风险分析

### 4.1 技术风险

**R-01：LLM 调用稳定性（高风险）**
- 描述：OpenAI/Claude API 存在限流、超时、服务中断风险
- 影响：Python Agent 核心功能完全依赖外部 LLM，单点故障
- 缓解：已设计降级机制（LLM 失败回退规则），但降级质量差
- 建议：实现重试+指数退避，支持多 provider 切换，本地模型备选

**R-02：代码改写安全性（高风险）**
- 描述：LLM 生成的代码可能引入安全漏洞、破坏性变更
- 影响：直接写入生产代码库，风险极高
- 缓解：ReviewerAgent 审查 + 审批门禁
- 建议：强制 diff 预览 + 人工审批，禁止自动合并到主分支

**R-03：工作区路径越权（高风险）**
- 描述：CoderAgent 的 `_choose_target_file` 逻辑简单，可能写入非预期路径
- 影响：文件系统破坏，数据丢失
- 缓解：FileTool 有 workspace allowlist 检查
- 建议：加强路径校验，所有写操作必须在 workspacePath 内

**R-04：Python Agent 无生产级错误处理（中风险）**
- 描述：多处 `except Exception` 宽泛捕获，错误信息可能丢失
- 影响：问题排查困难，静默失败
- 建议：结构化日志，区分可重试/不可重试错误

**R-05：数据库单点（中风险）**
- 描述：MySQL 无主从/集群配置
- 影响：数据库故障导致全系统不可用
- 建议：生产环境配置主从复制，考虑读写分离

**R-06：Redis 密码硬编码（中风险）**
- 描述：`docker-compose.yml` 中 Redis 密码为 `000000`，MySQL 密码同样简单
- 影响：开发配置泄露到生产环境
- 建议：生产环境使用 Secrets Manager，禁止硬编码凭证

### 4.2 架构风险

**R-07：Python Agent 与 Java Agent 职责重叠（中风险）**
- 描述：两个 Agent 都可以执行任务，但分工不清晰
- 影响：维护成本高，行为不一致
- 建议：明确分工：Python Agent 负责 AI 编排，Java Agent 负责本地执行

**R-08：事件 payload 无 schema 验证（中风险）**
- 描述：`TaskEvent.payload` 是 `Map<String, Object>`，无强类型约束
- 影响：各组件对 payload 结构理解不一致，难以维护
- 建议：为关键事件类型定义强类型 payload schema

**R-09：移动端 mock 数据与真实数据混用（低风险）**
- 描述：AppViewModel 中 mock 项目列表与真实项目混用
- 影响：测试时可能误用 mock 数据，掩盖真实问题
- 建议：明确区分 mock 模式和生产模式

### 4.3 交付风险

**R-10：核心功能（LLM 化）尚未实现（极高风险）**
- 描述：Python Agent 的 LLM 调用是整个产品的核心价值，当前完全缺失
- 影响：产品无法交付，所有演示依赖 mock
- 建议：优先实现 LLMClient + DiffUtils + 四个 Agent 的 LLM 化

**R-11：缺乏端到端测试（高风险）**
- 描述：各组件有单元测试，但无完整的 E2E 测试
- 影响：集成问题在生产才暴露
- 建议：实现 `scripts/smoke-test.ps1` 覆盖完整链路

---

## 五、优先级建议

### 立即执行（本周）

1. **实现 `llm_client.py`**（OpenAI + Claude 双 backend，失败降级）
2. **实现 `diff_utils.py`**（unified diff 生成 + 实质变更判断）
3. **升级 IntentAgent/PlannerAgent**（LLM 驱动，失败降级规则）
4. **升级 CoderAgent**（真实文件改写 + diff 输出）
5. **升级 ReviewerAgent**（基于 diff 的 LLM 审查）

### 短期（2周内）

6. **实现 Fix Loop**（测试失败自动修复，最多 3 次）
7. **产物存储持久化**（MinIO 或本地文件系统适配）
8. **移动端 diff 渲染**（FILE_PATCH_PREVIEW 可视化）
9. **端到端集成测试**（覆盖创建→执行→审批→产物完整链路）

### 中期（1个月内）

10. **JWT 短期 token + 刷新机制**
11. **project-scoped 资源级授权**
12. **语音输入集成**（Android SpeechRecognizer）
13. **分布式追踪**（traceId 贯穿所有组件）
14. **Python Agent 依赖管理**（requirements.txt + Docker 镜像）

---

## 六、架构亮点

尽管存在上述缺陷，项目架构设计有以下值得肯定的亮点：

1. **事件驱动 + 增量补流**：seq 机制保证弱网/断线恢复，无事件丢失
2. **审批强绑定**：command/cwd/inputsHash 三重校验，防止执行上下文漂移
3. **DAG 调度**：Agent 间依赖清晰，支持并行执行（review + test 并行）
4. **失败降级设计**：LLM 失败自动回退规则，系统持续可用
5. **幂等任务创建**：SHA-256 确定性 taskId，防止重复创建
6. **租约管理**：lease 过期自动回收，防止任务"孤儿化"
7. **分层架构**：Domain/Application/Ports/Adapters 清晰分离
8. **多模式支持**：移动端支持在线/离线双模式，开发体验好

---

## 七、移动端开发进度复核（2026-04-09）

本节用于“覆盖修正”第 2.4 与第 3.2 中已过时的移动端结论。

### 7.1 已确认完成（代码已落地）

1. 语音输入已实现（非缺失）
- `AppUi.kt` 已接入 `RecognizerIntent` 与麦克风交互。

2. 代码变更 diff 展示已实现（基础版）
- `FILE_PATCH_PREVIEW` 事件已渲染为逐行 diff（含 +/- 颜色区分）。

3. WebSocket 实时链路已实现（含重连 + 补流）
- 已有 `WebSocketClient`，CONNECT/SUBSCRIBE，断线重连，`lastSeq` 增量恢复。

4. 审批交互已实现
- 已有 `pendingApproval` 状态流、审批弹层与 `submitApproval` 调用。

5. 产物链路已实现（列表/预览/下载）
- 已接入 artifacts API，支持文本预览与下载。

### 7.2 当前真实缺口（移动端侧）

1. 发布流程仍是本地记录为主（mock）
- `recordPublishEntry()` 当前仍以本地历史记录方式写入，缺少“真实发布任务触发 + 服务端历史回拉”闭环。

2. 项目列表未对接真实 projects API
- 当前 `refreshProjectsInternal()` 仍以任务派生项目为主，缺少控制面项目列表同步。

3. LLM 专项可视化仍偏基础
- 对 `riskLevel/issues/errorCode/fixLoopAttempt/maxAttempts` 等字段尚未形成结构化卡片与聚合展示。

4. 移动端质量门禁不足
- 缺少 androidTest/UI 自动化，关键路径（语音、审批、事件流）缺少回归保障。

5. 通知能力缺失
- 无推送通知（审批请求、任务完成、失败告警），用户仍以“前台查看”为主。

6. 离线能力偏弱
- 当前以 DataStore 持久化为主，缺少 Room 级别的事件缓存与离线重放策略。

---

## 八、移动端新 PR 规划（结合当前分析）

目标：在“现有可用基础”上快速补齐移动端产品化闭环。

### 8.0 强制协作纪律（必须执行）

1. 工作区必须相互独立
- 每个 Agent 固定使用独立 `worktree` + 独立分支（禁止共用同一工作目录并行改动）。
- 每个 PR 只允许修改该 Agent 负责范围内的文件，跨域改动必须先拆分 PR。
- 禁止将其他 Agent 的未合并改动带入当前 PR。

2. 工作区必须保持干净
- 开发前执行一次 `git status --short --branch`，确认当前分支与改动范围。
- 提交前必须清理临时文件和无关变更，保证 PR 仅包含目标任务改动。
- 合并前必须满足“可复现 clean 状态”：切换到对应分支后可通过 `git status --short` 快速识别本 PR 的全部改动来源。

3. PR 门禁（不满足则不提审）
- `git diff --name-only` 仅包含本 PR 任务文件。
- 无无关 `??` 未跟踪目录/文件（如临时脚本、缓存、本地实验产物）。
- PR 描述中明确：负责 Agent、工作区路径、分支名、影响范围、回滚方案。

### Phase A（P0，本周）

1. `feat/a4-mob-real-publish-flow`
- 责任：Agent-4（移动端），Agent-1 配合控制面接口
- 范围：`mobile-app/**`（必要时 `control-plane-spring/**`）
- 内容：
  - 将发布入口从 `recordPublishEntry()` mock 改为真实 API 调用。
  - 发布历史优先读服务端，失败回落本地缓存。
- 验收：
  - 移动端可发起真实发布，收到 deploy 事件后自动更新历史。

2. `feat/a4-mob-projects-api-sync-v2`
- 责任：Agent-4（移动端），依赖 Agent-1 项目列表 API
- 范围：`mobile-app/**`
- 内容：
  - 对接 `/api/v1/projects`（或统一项目列表接口）。
  - 本地派生项目改为 fallback 逻辑。
- 验收：
  - 登录后项目列表来自服务端；离线时可降级 fallback。

### Phase B（P1，1-2 周）

3. `feat/a4-mob-review-fixloop-cards`
- 责任：Agent-4
- 范围：`mobile-app/**`
- 内容：
  - 新增结构化事件卡片：`riskLevel/issues/errorCode/fixLoopAttempt/maxAttempts`。
  - 任务详情页增加“修复进度时间线”。
- 验收：
  - LLM 任务失败/重试路径在移动端可一眼定位失败原因与重试次数。

4. `test/a4-mob-critical-ui-regression`
- 责任：Agent-4
- 范围：`mobile-app/**`
- 内容：
  - 补齐关键 UI 自动化：语音输入、审批弹层、事件流展示、产物预览。
- 验收：
  - androidTest 可稳定通过，覆盖核心路径。

### Phase C（P2，2-4 周）

5. `feat/a4-mob-push-notification`
- 责任：Agent-4，Agent-1 配合通知触发
- 范围：`mobile-app/**`（必要时 `control-plane-spring/**`）
- 内容：
  - 任务完成/失败、审批待处理推送通知。
- 验收：
  - App 后台或锁屏状态可收到关键任务通知。

6. `feat/a4-mob-offline-room-event-cache`
- 责任：Agent-4
- 范围：`mobile-app/**`
- 内容：
  - 引入 Room，沉淀任务事件缓存、离线浏览与重连补偿。
- 验收：
  - 弱网/离线后可查看最近任务与事件，恢复后自动对齐服务端。

### 建议合并顺序

1. `feat/a4-mob-real-publish-flow`
2. `feat/a4-mob-projects-api-sync-v2`
3. `feat/a4-mob-review-fixloop-cards`
4. `test/a4-mob-critical-ui-regression`
5. `feat/a4-mob-push-notification`
6. `feat/a4-mob-offline-room-event-cache`
