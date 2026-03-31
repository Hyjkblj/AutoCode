# MobileVoice-CodeOps 路线图（按优先级）

本文件用于跟踪本仓库从 MVP 到工业级的开发任务清单与验收标准，强调 **高内聚、低耦合**（通过端口/适配器抽象隔离基础设施与业务编排）。

## 当前状态（已具备）

- 控制平面（Spring Boot）：任务创建/幂等、队列分发、事件落库与 WS 广播、审批流、审计
- PC Agent（Java）：注册/心跳、轮询领取任务、安全白名单 + 审批等待、命令执行与事件回传
- 本地验证：`scripts/smoke-test.ps1` 可跑通创建→审批→DONE

## P0（立刻做：把 MVP 从“能跑”升级为“有真实产物 + 更安全 + 更稳”）

### P0-1 任务加入工作区上下文（workspacePath）

- **目标**：任务携带 `workspacePath`（或 `projectPath`），Agent 使用该 `cwd` 执行工具/命令，并把该上下文纳入审批绑定。
- **涉及模块**
  - control-plane：`CreateTaskRequest`、`TaskEntity`、`TaskSummary`、`TaskService`
  - agent：`TaskExecutor`（执行时设置 cwd）
- **验收（DoD）**
  - 创建任务时可指定 workspacePath
  - 事件中能看到被执行的 cwd
  - 在非 git 仓库目录不会再误执行 git 命令（可通过 workspacePath 指向真实 repo 验证）

### P0-2 真实 FILE_PATCH_PREVIEW（产物闭环）

- **目标**：Agent 产生真实 `FILE_PATCH_PREVIEW`（例如基于 `git diff --stat` / `git diff`），控制平面 `/artifacts` 能展示真实变更摘要。
- **涉及模块**
  - agent：新增 `GitDiffCollector`（或 tool 模块），产出 patch preview payload
  - control-plane：复用现有 `ArtifactQueryService` 聚合逻辑
- **验收（DoD）**
  - `GET /api/v1/tasks/{taskId}/artifacts` 返回至少 1 条真实 patch preview

### P0-3 Agent 注册/心跳幂等 upsert

- **目标**：重复 register/heartbeat 不再触发主键冲突；节点信息可覆盖更新。
- **涉及模块**
  - control-plane：`AgentRegistryService`
- **验收（DoD）**
  - 多次 register 同一 nodeId 不报错

### P0-4 审批强绑定与校验（防漂移）

- **目标**：审批时展示/记录的 command/cwd 等必须与后续执行一致；不一致时拒绝执行并审计。
- **涉及模块**
  - control-plane：审批记录扩展（可先基于事件 payload）
  - agent：执行前再次声明将执行的上下文（或 runId）
- **验收（DoD）**
  - 人为篡改执行上下文会被拦截

### P0-5 分发语义与重入保护

- **目标**：明确至少一次/至多一次语义；防止同任务被重复领取/重复执行导致状态错乱。
- **涉及模块**
  - control-plane：`pollNextTaskForNode` 增加 lease/超时/重新入队策略
- **验收（DoD）**
  - 在异常/重启场景下不会出现“无主任务”或“多节点重复执行”不可控

## P1（工程化：把“执行器”升级为“可扩展的工具/技能运行时”）

- **P1-1 Tool/Skill 注册表**：在 agent 引入工具注册表（schema/权限/审批策略），替代硬编码 `command.exec`
- **P1-2 策略引擎化**：目录白名单、命令白名单、网络访问、提权等策略配置化
- **P1-3 可观测性**：结构化日志/指标/traceId 贯穿事件
- **P1-4 断线恢复**：统一 seq（lastEventId→lastSeq 兼容）
- **P1-5 OpenAPI + 契约测试**：接口与事件 schema 版本化

## P2（规模化：多节点、多角色、可交付）

- **P2-1 MQ 适配**：队列实现扩展到 Rabbit/Kafka 等
- **P2-2 多 Profile 与路由**：coder/reviewer/tester + lane 串行
- **P2-3 Agent 工业化交付**：服务化运行、自动更新/回滚
- **P2-4 安全加固**：TLS/mTLS、token 轮换与吊销、审计不可篡改

