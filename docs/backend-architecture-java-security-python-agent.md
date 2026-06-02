# AutoCode 后端技术架构全景梳理

## 0. 文档范围与目标

本文基于当前仓库代码（`control-plane-spring`、`pc-agent-java`、`python-agent`、`shared-protocol`、`docker-compose.yml`）进行后端技术架构梳理，重点覆盖：

- 业务架构与主链路（任务创建、调度、执行、审批、工件、审计）
- Java 安全策略（控制面安全 + Java 代理执行安全）
- Python 智能体设计（多 Agent 编排、DAG、Memory、工具调用）
- 核心算法逻辑（含伪代码）
- 跨语言协议契约（shared-protocol）

## 1. 系统总体架构

### 1.1 核心模块

- `control-plane-spring`
  - 控制平面，负责任务生命周期、事件摄取、审批、审计、工件管理、WebSocket 广播、RBAC 鉴权。
- `pc-agent-java`
  - 节点代理与本地执行面，负责任务执行、策略校验、审批等待、上报事件、运行时描述符/工件上报。
  - 同时提供 `127.0.0.1` 沙箱 HTTP 服务给 Python 代理调用。
- `python-agent`
  - AI 智能体编排层，执行 Intent/Plan/Coder/Reviewer/Tester 流程，调用 Java 沙箱执行命令，聚合结果并上报。
- `shared-protocol`
  - 跨模块共享 DTO、事件类型、JSON Schema 与契约校验器，确保 Java/Python/控制面语义一致。

### 1.2 部署关系（docker-compose）

- `control-plane` 使用 MySQL + Redis。
- `pc-agent-java` 连接控制平面，开启本地沙箱（默认 `127.0.0.1:18080`）。
- `python-agent` 使用 `network_mode: service:pc-agent-java`，通过 `http://127.0.0.1:18080/sandbox/execute` 调用 Java 沙箱。

这形成了典型的“双代理分层”：

- Python 负责智能编排与 LLM 交互。
- Java 负责执行与安全控制面（策略链 + 沙箱 + 审批门控）。

## 2. 业务架构与主流程

### 2.1 任务生命周期主链路

1. Operator 创建任务：`POST /api/v1/tasks`
2. 控制平面持久化任务（`QUEUED`）并入队，写入 `TASK_CREATED` 事件。
3. Agent 轮询领取：`GET /api/v1/agent/tasks/next?nodeId=&profile=`
4. 控制平面原子 claim 任务，置为 `RUNNING`，写入 `TASK_STARTED`。
5. Agent（Python/Java）执行并持续上报事件：`ASSISTANT_OUTPUT / TOOL_* / APPROVAL_* / FILE_PATCH_PREVIEW / ARTIFACT_READY / TASK_DONE|TASK_FAILED ...`
6. 控制平面摄取事件、推进状态机、审计记录、事务后 WebSocket 广播 `/topic/tasks/{taskId}`。

### 2.2 审批主链路

1. 代理侧策略判定需审批时发 `APPROVAL_REQUIRED`（包含 `approvalId`、`context`、`riskScore`、`requiredPolicies`）。
2. Operator 审批：`POST /api/v1/tasks/{taskId}/approval`
3. 控制平面写 `APPROVAL_RESULT` 并更新任务状态（`RUNNING` 或 `CANCELED`）。
4. 代理轮询 `GET /api/v1/agent/tasks/{taskId}/approval`，拿到 `approve/reject/pending` 后继续或失败。

### 2.3 工件主链路

1. 代理上传二进制工件：`POST /api/v1/tasks/{taskId}/artifacts`（multipart）。
2. 控制平面持久化工件元数据 + 文件（本地存储适配器）。
3. 任务事件发 `ARTIFACT_READY`（包含 `artifact` 元数据、`kind`）。
4. Operator 下载/预览：`/download`、`/preview`。
5. Web 类工件可托管为站点：`/site-url` 与 `/site/**`（含 zip 解包、入口页识别、SPA 回退）。

## 3. Control Plane 技术架构（Spring）

### 3.1 分层职责

- API 层：`TaskController`、`AgentController`、`ArtifactsController`、`ProjectController`、`AuditController`
- 业务层：
  - `TaskService`：核心状态机与事件编排
  - `AgentRegistryService`：节点注册与心跳在线态
  - `ArtifactsService`/`HostedArtifactSiteService`：工件与托管站点
  - `AuditService`：审计日志与 hash 链
- 基础设施层：
  - JPA Repository（任务、事件、审批、审计、工件、RBAC）
  - 队列适配器（Redis / Rabbit / InMemory）
  - WebSocket 发布器（事务后广播）

### 3.2 任务状态机与事件折叠（TaskService）

`TaskService.ingestAgentEvent(...)` 的关键机制：

- 行级锁读取任务（for update），保证并发摄取下序列稳定。
- `eventId` 去重（幂等）。
- 统一补齐事件字段（task/session/assistant/timestamp）。
- 控制面分配 `seq`，并维护 `next_seq`。
- 按事件类型折叠任务状态：
  - `APPROVAL_REQUIRED` -> `WAITING_APPROVAL/RUNNING/CANCELED`
  - `DEPLOY_PLAN` -> `RUNNING`（需先过 deploy 授权）
  - `DEPLOY_RESULT` -> `RUNNING/DONE/FAILED/CANCELED`
  - `TASK_DONE` -> `DONE`
  - `TASK_FAILED` -> `FAILED` + retry backoff
- 事务提交后才广播事件，避免“幽灵事件”。

### 3.3 调度与租约

- 支持两种模式：
  - `db`：直接从 DB 选择“可领取”任务（默认）
  - `queue`：从队列弹出并 claim
- 原子 claim SQL：仅当 `status='QUEUED'` 才能从 DB 置为 `RUNNING`。
- 租约恢复：
  - `RUNNING` 任务 lease 过期后可回收为 `QUEUED` 并重新入队。
  - 定时任务 `scheduledLeaseRecovery()` 兜底恢复。
- Lane 串行化：
  - 同 `session_key` 若已有 `RUNNING` 任务，则新任务延后，避免并行冲突。

### 3.4 数据模型与迁移

关键表：

- `tasks`：任务主状态、租约、重试、profile/lane、审批绑定
- `task_events`：事件溯源日志（`task_id + seq_num` 唯一）
- `approvals`：审批决定与审批上下文 JSON
- `audit_logs`：审计记录 + `prev_hash/entry_hash`
- `artifacts`：工件元数据与存储路径
- RBAC：`users/roles/user_roles/projects/project_memberships`

Flyway V1~V13 演进覆盖：工作区、审批上下文、租约、profile/lane、RBAC、审计 hash 链、重试字段、事件唯一序列、工件表、agent_nodes 兼容回填。

## 4. Java 安全策略（重点）

## 4.1 控制平面认证与授权

JWT 模式：`JwtSecurityConfig + OAuth2 Resource Server`

关键能力：

- JWT `roles` -> Spring Authorities（`RolesClaimAuthoritiesConverter`）
- JWT 模式下兼容遗留 `X-Agent-Token`（`JwtAgentTokenAuthAdapterFilter`）
- 方法级项目授权：`@PreAuthorize("@projectAuthz...")`
- 提权角色可跨项目访问（`mvp.auth.elevated-authorities`）
- 防资源枚举：任务/工件/审计若无权限，很多接口返回 `404` 而非 `403`

## 4.2 mTLS 分域强制

`AgentMtlsEnforcementFilter` 仅对 `/api/v1/agent/**` 强制证书（按配置开关），不把 operator 全局拉入 mTLS，兼顾安全与可用性。

## 4.3 WebSocket 安全

- `JwtWebSocketAuthInterceptor`
  - `CONNECT` 验证 Bearer JWT + roles
- 未认证 `SUBSCRIBE/SEND` 拒绝

## 4.4 审批上下文强绑定（关键安全点）

控制面会持久化审批上下文（`action/tool/workspaceRef/inputsHash/...`），并在关键事件做一致性校验：

- `TOOL_START(command.exec)` 与审批上下文不一致 -> 标记失败
- `DEPLOY_PLAN` 在已审批任务上必须上下文匹配
- Deploy 事件在审批未通过时拒绝（审计 `deploy.authz.denied`）

这防止“审批后换命令/换上下文”的漂移攻击。

## 4.5 Java 代理执行安全（策略链）

`TaskExecutor/SandboxExecutionService` 使用组合策略链（先拒绝即终止）：

1. `ElevationDetectionPolicy`：拦截 `sudo/runas/pkexec/...`
2. `EnvVarAccessPolicy`：拦截敏感密钥变量引用（OPENAI_API_KEY/GITHUB_TOKEN/...）
3. `NetworkAccessPolicy`：`MVP_NETWORK_ALLOWED=false` 时拦截网络指令特征
4. `FileReadWritePolicy`：写操作路径必须在允许前缀内，阻断 root 级破坏写
5. `WorkspaceAllowlistPolicy`：`cwd` 必须在允许工作区前缀内

此外 `CommandSafetyPolicy` 做命令前缀白名单 + 高风险审批触发关键词（deploy/rm/curl 等）。

## 4.6 本地沙箱安全边界

- `SandboxHttpServer` 强制只监听 `127.0.0.1`
- 暴露最小面：`/sandbox/health`、`/sandbox/tools`、`/sandbox/execute`
- 请求/响应都经过 shared-protocol 契约校验
- 执行前仍走 Java 策略链 + 可选审批，不允许 Python 直接绕过安全策略

## 4.7 工件访问安全

- 默认共享 token 校验下载（可配置“已认证用户免 token”）
- hosted site 访问支持 token/cookie
- 路径标准化 + zip entry 校验，阻断路径穿越
- 站点路由支持 SPA fallback，但仍限定在托管目录内

## 5. Python 智能体设计（重点）

### 5.1 运行入口与生命周期

- `main.py` 读取环境变量 -> 构建 `RunnerConfig`
- `AgentRunner.tick()`：
  - 确保注册
  - 到期心跳
  - 轮询任务
  - 分发到 `AgentOrchestrator.handle_task()`

### 5.2 多 Agent 编排结构

`AgentOrchestrator` 组合：

- `IntentAgent`：意图识别（deploy/test/code_change/analyze）
- `PlannerAgent`：产出 `plan_name + steps`
- `CoderAgent`：代码修改或 web 模板生成
- `ReviewerAgent`：评审（LLM 或 blocker fallback）
- `TesterAgent`：通过 Java 沙箱执行测试命令，带重试
- `DagScheduler`：并行执行 review/test
- `RedisMemory`：跨任务记忆（测试命令/部署命令复用）

### 5.3 Code Change 主流程

1. 读取 Memory 历史并注入提示（如 `memoryLastTestCommand`）
2. Intent 判定 + Planner 产计划
3. `CoderAgent.execute` 产出改动并发 `FILE_PATCH_PREVIEW`
4. `DagScheduler` 并行执行：
   - Review：`ReviewerAgent.review`
   - Test：`TesterAgent.execute`（沙箱命令 + 重试）
5. 任一步失败发 `TASK_FAILED`，全部通过发 `TASK_DONE`
6. 若是 web 目标，打包 `export.zip` 并上传，发 `ARTIFACT_READY`

### 5.4 Web 生成路径

- `target=web` 时强制走 code_change pipeline
- `WebTemplateGenerator` 优先 LLM 生成 `index.html/styles.css/app.js/README.generated.md`
- LLM 不可用时自动 fallback 模板
- `artifact_utils.build_export_zip` 打包并计算 sha256/size

### 5.5 Python -> Java 沙箱调用模型

`ExecTool.execute()` 请求 `/sandbox/execute`，字段含：

- `taskId/command/cwd/prompt`
- `tool`（deploy 用 `deploy.execute`，其他默认 `command.exec`）
- `assistant/sessionId/sessionKey/approvalTimeoutSeconds`

返回统一 `ExecResult`：

- `ok/status/exitCode/output/retryable/reason`
- `tool/toolVersion/traceId/runId/approvalId`

### 5.6 Memory 设计

`RedisMemory`：

- key 生成优先级：`projectId -> project -> workspacePath -> workspaceRef -> sessionId -> sessionKey -> default`
- Redis 可用时用 Redis list；不可用自动降级进程内内存
- `append()` 固定保留 `max_entries`（默认 50）
- `recent(limit)` 用于为下一任务注入历史命令与上下文

### 5.7 Python 核心算法伪代码

```text
handle_task(task):
  history = memory.recent(project_key(task), 5)
  apply_memory_hints(task, history)
  normalize_target(task)
  if target 非空且 != web:
    TASK_FAILED(unsupported_target); memory.append(failed); return

  decision = IntentAgent.infer(prompt)
  if target==web and decision != code_change:
    force decision=code_change
  emit IntentAgent

  plan = PlannerAgent.build_plan(prompt, decision)
  emit PlannerAgent

  if decision == code_change:
    ok = CoderAgent.execute(...)
    if !ok: fail(coder_failed)
    dag_results = DAG.run([coder_done, review, test])
    if review reject: fail(review_rejected)
    if test fail: fail(test_failed)
    if web: publish artifact
    TASK_DONE(coded_reviewed_tested)
    memory.append(done)
    return

  if decision in {deploy, test}:
    result = ExecTool.execute(...)
    if ok: TASK_DONE(executed) else TASK_FAILED(...)
    memory.append(...)
    return

  TASK_DONE(planned)
```

```text
DAG.run(nodes):
  校验节点唯一 + 依赖存在
  while 仍有未完成:
    ready = 所有依赖已完成节点
    若 ready 为空 -> 环或依赖异常
    并发执行 ready (ThreadPoolExecutor)
    若任一节点异常 -> 立即抛错终止
    标记 ready 完成并写结果
  return results
```

## 6. shared-protocol 契约层

### 6.1 统一事件类型（EventType）

包括：`TASK_CREATED/TASK_STARTED/ASSISTANT_OUTPUT/TOOL_START/TOOL_END/FILE_PATCH_PREVIEW/SPEC_PROPOSED/BUILD_*/APPROVAL_*/DEPLOY_*/ARTIFACT_READY/TASK_DONE/TASK_FAILED/HEARTBEAT`

### 6.2 关键模型

- `TaskEvent`：`eventId/taskId/type/timestamp/seq/eventVersion/payload`
- `SandboxExecuteRequest/Response`
- `SandboxToolsResponse`
- `ArtifactMetadata/ArtifactManifest`
- `ServiceRuntimeDescriptor`
- `ApprovalContext/ApprovalDecision`

### 6.3 契约校验器

- `TaskEventContractValidator`
- `SandboxExecuteContractValidator`
- `SandboxHttpContractValidator`
- `ToolManifestContractValidator`
- `ArtifactManifestContractValidator`
- `ServiceRuntimeDescriptorContractValidator`

价值：把“字段完整性、可选扩展、取值边界”前置为可测试契约，避免 Java/Python 漂移。

## 7. 核心算法逻辑（Java 侧）

### 7.1 控制平面任务创建与幂等

```text
createTask(request, idemKey):
  if idemKey 已存在映射:
    return mappedTask
  taskId = hash(idemKey + projectId) 或随机ID
  插入 tasks(status=QUEUED, nextSeq=1)
  入队
  记录 idempotency_records
  写 TASK_CREATED 系统事件
  写审计 task.create
  return TaskSummary
```

### 7.2 任务领取与租约恢复

```text
pollNextTaskForNode(node, profile):
  取下一条可执行 QUEUED 任务(含 profile 与 lane 约束)
  claimQueuedTask 原子更新 status=RUNNING + lease_expires_at
  写 TASK_STARTED
  return task

scheduledLeaseRecovery():
  扫描 RUNNING 且 lease 过期任务
  requeueIfLeaseExpired 成功则重新入队 + 审计
```

### 7.3 事件摄取与状态折叠

```text
ingestAgentEvent(taskId, event):
  校验契约 -> 锁任务行 -> eventId 去重
  规范化 event + 分配 seq
  updateTaskStateFromEvent(task, event)
  持久化 task + task_event
  afterCommit 广播 WS
  审计 event.ingest
```

### 7.4 Java 节点执行链

```text
TaskExecutor.execute(task):
  intent = router.route(task)
  skill = skillRegistry.resolve(intent.skill)
  skill.execute(context)

executeRoutedIntent(...):
  构造 ToolCall
  invocationPolicy.evaluate -> deny 则 TASK_FAILED(policy_denied)
  tool.policy.isAllowed -> deny 则 TASK_FAILED(command_not_allowed)
  需要审批则发 APPROVAL_REQUIRED 并 waitForApproval
  发 TOOL_START
  tool.execute
  发 TOOL_END
  若失败映射 TASK_FAILED(exec_timeout/nonzero/exec_failed)
  可选收集 git diff + post-success artifact + runtime descriptor + deploy 事件
  最终 TASK_DONE(success)
```

## 8. 观测与审计

- 控制面指标：`tasks_created`、`tasks_polled`、`events_ingested`、`lease_requeued`、`poll_duration`
- 审计链：
  - 每条审计记录包含 `prev_hash` 与 `entry_hash`
  - `AuditController /api/v1/audits/export` 可导出并校验链连续性 `chainValid`

## 9. 关键实现差异（Python 现状 vs 测试期望）

当前 `python-agent` 中存在明显“代码与测试不同步”现象，主要包括：

1. `IntentAgent`
   - 测试期望：支持 LLM 分类 + fallback
   - 现实现：规则关键词 + key 缺失判断（未直接调用 `LLMClient.chat`）
2. `AgentOrchestrator`
   - 测试期望：Fix Loop、`errorCode` 标准化、`SPEC_PROPOSED/BUILD_*` 事件、`unsupported_export_mode` 等
   - 现实现：主流程为 Intent/Plan/Coder/DAG + artifact，缺失上述增强能力
3. 测试中引用的 `_resolve_fix_loop_max_attempts`、`_error_code_from_reason` 在现文件中不存在

这意味着：架构方向已经在测试中定义得更前，但生产实现尚未完全跟上。

## 10. 架构结论

1. 该系统是“控制平面 + 执行平面（Java）+ 智能编排平面（Python）”三层协作架构。
2. Java 侧安全设计较完整，形成了“认证授权 + mTLS 分域 + 工具策略链 + 审批上下文绑定 + 审计链”的纵深防御。
3. Python 侧已经具备多 Agent 编排、并行 DAG、记忆增强和工件生成能力，是业务智能化的核心入口。
4. shared-protocol 作为跨语言契约中枢，保障了事件/沙箱/工件语义一致，是平台可演进性的关键基础。
5. 当前最需要推进的是 Python 编排能力与测试契约对齐，避免“测试架构领先、运行时能力滞后”的长期分叉。

