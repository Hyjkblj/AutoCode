# 企业级软件开发方案（基于已验证 MVP）

> 目标：在现有 **Control Plane（Spring Boot）+ PC Agent（Java）** MVP 验证通过的基础上，按**高内聚、低耦合**与**最佳实践**演进到可在企业环境部署、审计合规、可扩展、多节点高可用的产品形态。  
> 方法：以 **PR（Pull Request）为单位**分阶段交付；每个 PR 都能独立合并、回滚、验收。

---

## 0. 现状基线（你们已经具备）

- **任务闭环**：创建→分发→执行→事件回传→审批→完成/失败
- **稳态分发**：DB 原子 claim + lease/过期回收/重入队
- **事件系统**：事件落库 + `seq` 增量补流（`lastSeq`，兼容 `lastEventId`）
- **安全（MVP）**：审批上下文强绑定；token 轮换/吊销（允许列表 + revoked）
- **Agent 工程化基础**：Tool 注册表、策略雏形（workspace allowlist）、配置热更新、traceId/runId
- **接口契约**：OpenAPI (`/v3/api-docs`) + 契约测试
- **队列适配**：`redis / inmem / rabbit`（可配置）

---

## 1. 目标架构（高内聚低耦合）

### 1.1 分层与边界

- **Domain（领域层）**：任务、审批、审计、路由、策略等核心业务规则；禁止依赖 Spring/DB/Redis/Rabbit 客户端细节
- **Application（应用编排层）**：用例（CreateTask / PollTask / IngestEvent / Approve / Cancel / QueryArtifacts）
- **Ports（端口）**：队列、事件存储、审计存储、策略决策、身份鉴权、证书与密钥、通知等接口
- **Adapters（适配器）**：JPA/Redis/Rabbit/WebSocket/HTTP 等基础设施实现

### 1.2 模块化建议（仓库内）

- `shared-protocol`：API DTO + 事件 schema + 版本兼容策略
- `control-plane-spring`：
  - `domain/`（纯 Java 领域模型与规则）
  - `app/`（用例/服务编排）
  - `ports/`（接口）
  - `adapters/`（JPA/Redis/Rabbit/WebSocket/HTTP）
- `pc-agent-java`：
  - `tool/`（Tool/Skill runtime）
  - `policy/`（策略引擎）
  - `client/`（Control Plane API client）
  - `runtime/`（主循环、重试、恢复）

> 说明：当前实现已具备端口/适配器雏形（如 `TaskQueuePort`），后续 PR 将进一步“去框架化”领域逻辑并收敛依赖方向。

---

## 2. 非功能性目标（企业级门槛）

- **安全**：TLS/mTLS、JWT/RBAC、短期 token、吊销、最小权限、审批不可绕过、审计不可篡改
- **可用性**：多实例 Control Plane，队列/DB 高可用；Agent 断线恢复；幂等与去重
- **可观测性**：结构化日志、指标、分布式追踪（OTel），SLO 与告警
- **可扩展**：工具/技能插件化，策略配置化，队列可插拔，路由与 lane 可演进
- **可交付**：Agent 服务化（Windows service）、安装包、自动更新/回滚

---

## 2.1 安全风险清单（基于当前方案的潜在风险与优化）

> 目的：把“企业级”阶段不可接受的风险显式列出，并将对策固化为 PR 顺序与安全门禁（Security Gates）。

### 2.1.1 认证与授权（Identity & Access）

- **风险：长生命周期共享 token（或单一 token）**
  - **影响**：凭证泄漏即全权访问；难做最小权限；无法做到人员级审计。
  - **优化**：引入 **短期 JWT + 刷新机制 + 吊销**，并落地 **RBAC**（Operator/Viewer/Admin）。Agent 使用独立身份（mTLS 或专用凭证）。

- **风险：缺少资源级授权（project/task 维度）**
  - **影响**：同一 operator token 可访问所有 task；跨项目越权读取/审批。
  - **优化**：至少实现 project-scoped policy（用户/角色与 project 绑定），并在关键接口（events/artifacts/approval）强制校验。

### 2.1.2 传输安全（Transport）

- **风险：未强制 TLS/mTLS**
  - **影响**：内网也可能被旁路抓包/篡改；审批与执行上下文可能被劫持；token 易被复用。
  - **优化**：Control Plane 强制 TLS；Agent↔Control Plane 建议 **mTLS**（企业内可强制）。

### 2.1.3 Agent 执行面（Execution Surface，最大风险面）

- **风险：命令执行是天然高危能力（RCE）**
  - **影响**：被滥用可读写代码仓库/凭证/内网资产。
  - **优化**：
    - 策略引擎升级：目录白名单、命令白名单、网络访问、提权、环境变量访问、文件读写范围
    - Tool 执行沙箱：限制工作目录、超时、输出、并发、可执行文件路径
    - 审批强绑定继续增强：把 `tool/command/cwd/runId`（可选 `hash`）纳入审批上下文并在服务端强校验

### 2.1.4 供应链与发布（Supply Chain）

- **风险：自动更新链路被劫持**
  - **影响**：下发恶意 Agent，直接获得企业终端执行权限。
  - **优化**：更新包与发布元数据必须 **签名校验**（离线公钥内置/可信根），并提供可靠回滚。

### 2.1.5 审计与合规（Audit & Compliance）

- **风险：审计可被篡改/删除**
  - **影响**：无法满足合规/取证；事故不可追溯。
  - **优化**：审计 hash chain/签名 + 归档（WORM/对象存储）；关键状态迁移与审批链路必须写审计且不可跳过。

### 2.1.6 路由与队列（Routing & Queue）

- **风险：profile/lane 的“重新入队”带来的抖动与饥饿**
  - **影响**：任务长期得不到执行；可能形成 DoS 放大（高频空转）。
  - **优化**：引入调度器/按 profile 分队列；lane 使用明确的公平性策略（backoff/优先级/限流）。

---

## 2.2 安全门禁（Security Gates，强制执行）

- **G1（设计门禁）**：每个 PR 必须说明新增/变更的攻击面与威胁点、默认安全姿态、回滚方案
- **G2（测试门禁）**
  - 认证授权测试：RBAC + 资源级授权（project/task）
  - 审批绕过测试：审批上下文漂移必须失败（server-side）
  - Agent 策略拒绝测试：cwd/命令/网络/提权
- **G3（依赖门禁）**：新增依赖必须最小化并说明用途；禁止把 secrets 写入仓库
- **G4（发布门禁）**：安装包/更新包必须签名；校验失败禁止执行/覆盖

---

## 3. PR 规划（推荐顺序）

> 约定：每个 PR 都包含 **目标、范围、数据迁移、测试/验收 DoD、风险与回滚点**。

### 3.1 安全优先的执行顺序（对现有 PR 的优化建议）

为避免“在安全底座未完成前就扩大攻击面”，建议将 PR 执行顺序调整为：

1. **PR-04 安全基线 v1（TLS + JWT/RBAC）**
2. **PR-05 mTLS（Agent ↔ Control Plane）**
3. **PR-06 审计不可篡改（WORM/签名链）**
4. **PR-08 Tool/Skill 插件化（增加沙箱/权限/审批策略）**
5. 其余 PR（领域抽取、lane 调度、MQ 抽象、可观测性、服务化、自动更新）

并且：**PR-10 自动更新/回滚** 在企业环境必须和“签名校验 + 可信根管理”绑定一起交付，否则属于高风险交付链路。

---

## 3.2 PR 规划按端拆分（前端/后端/Agent）

> 说明：这里的“前端”既包含 **Web 控制台**（推荐用于企业管理/审批/审计），也包含 **Android 客户端**（语音入口与移动审批）。  
> 你们当前仓库主要是后端与 Agent，因此前端 PR 以“接口对齐 + 验收页面/能力”为主进行规划。

### 3.2.1 后端 PR（Control Plane / API / Persistence）

#### BE-PR-01：安全基线 v1（TLS + JWT/RBAC + 资源级授权）

- **目标**：企业级身份与权限底座，替代共享 token
- **范围**：Spring Security、JWT（短期）签发/校验、RBAC、project/task 资源级授权
- **数据**：新增 `users/roles/credentials`（或等价）表（Flyway）
- **DoD**：关键接口权限测试覆盖（create/query/events/artifacts/approval/agent endpoints）

#### BE-PR-02：mTLS 支持（服务端）

- **目标**：启用 TLS，并可选强制校验客户端证书（Agent）
- **范围**：server TLS、client cert 校验开关、证书配置与文档
- **实现备注（本仓库当前落地）**
  - 通过 `mvp.mtls.required-for-agent=true` 启用“**仅对 `/api/v1/agent/**` 强制 mTLS**”的应用层校验（不影响 operator/UI 调用）
  - TLS 终止与证书校验仍建议在网关/Ingress 层或通过 `server.ssl.*` 配置开启（生产环境建议强制 HTTPS）
  - 后续与 `AG-PR-01`（Agent mTLS 客户端）联动，把共享 token 逐步替换为证书绑定身份

#### BE-PR-03：审计不可篡改（hash chain/签名 + 归档接口）

- **目标**：审计可校验、可取证、可归档
- **范围**：audit_log 扩展 `prev_hash/hash/signature`（或新表）；归档导出 API
- **实现备注（本仓库当前落地）**
  - 先落地 **hash chain**：`audit_logs.prev_hash` + `audit_logs.entry_hash`，每条审计记录包含上一条的 hash
  - 对外提供归档导出：`GET /api/v1/audits/export?taskId=...`（返回 items + chainValid）
  - “签名链 / WORM” 可在后续迭代补齐（建议结合 KMS/HSM 与对象存储 WORM 策略）

#### BE-PR-04：lane/profile 调度器（避免 re-enqueue 抖动 + 抗饥饿）

- **目标**：公平性与可用性，避免队列空转导致 DoS 放大
- **范围**：按 profile 分队列或调度器；lane 串行严格保证；backoff/优先级/限流
- **实现备注（本仓库当前落地）**
  - 新增 `mvp.scheduler.mode=db`（默认），`pollNextTaskForNode` 直接从 DB 按 `created_at` 选择下一条**满足 profile/lane 条件**的 `QUEUED` 任务并原子 claim
  - 好处：避免 profile/lane 不匹配时的“出队→再入队”抖动与空转；公平性更稳定
  - `mvp.scheduler.mode=queue` 仍保留（兼容旧行为/实验对比）

#### BE-PR-05：队列语义标准化（ack/nack/visibility timeout）

- **目标**：统一 Redis/Rabbit/Kafka 的至少一次语义与可见性超时
- **范围**：扩展 `TaskQueuePort`（ack/nack/requeue/lease）；适配器对齐；文档 + 测试
- **实现备注（本仓库当前落地）**
  - `TaskQueuePort` 扩展为 `pollMessage()`（带 receipt）+ `ack(receipt)` + `nack(receipt, requeue)`
  - `TaskService` 的 `queue` 模式：**claim 成功才 ack**；profile/lane 不匹配时 nack+requeue，避免任务“无确认丢失”
  - Redis 适配器用 `hash(inflight)` 近似实现 in-flight（用于本仓库 MVP）；Rabbit 适配器在 `RabbitTemplate.receiveAndConvert` 场景下 ack/nack 为 best-effort（生产建议 listener + 手动 ack）

#### BE-PR-06：事件与协议稳定化（schema versioning + strict validation）

- **目标**：防协议漂移；事件 payload 关键字段（traceId/runId/tool/approvalContext）规范化
- **范围**：shared-protocol 增强；control-plane 对事件 payload 做校验与兼容策略
- **实现备注（本仓库当前落地）**
  - 在控制平面侧新增 `TaskEventValidator`：校验 `eventVersion`（当前仅支持 v1）与类型必填字段
  - 不符合协议的 Agent 事件将返回 HTTP 400（避免脏事件落库污染回放）
  - 对 `FILE_PATCH_PREVIEW` 做了向后兼容：允许 `patch` 或旧格式 `file/added/removed`

#### BE-PR-07：可观测性 v1（指标 + OTel）

- **目标**：可运维、可排障
- **范围**：Micrometer 指标、关键延迟/失败率；OTel trace（后端）
- **实现备注（本仓库当前落地）**
  - 指标：开启 `actuator/prometheus`，并补充核心业务指标（创建任务/派发任务/事件摄取/lease 回收/派发耗时）
  - Trace：接入 Micrometer Tracing（Otel bridge），支持 OTLP 导出（`management.otlp.tracing.endpoint`）

---

### 3.2.2 Agent PR（PC Agent / Tool Runtime / Policy / Delivery）

#### AG-PR-01：mTLS/JWT 客户端接入（Agent 身份）

- **依赖**：BE-PR-01/BE-PR-02
- **目标**：Agent 身份不再依赖共享 token；可被证书/凭证绑定
- **范围**：OkHttp TLS/mTLS；JWT 获取/刷新；失败退避与重连

#### AG-PR-02：策略引擎深化（最小权限运行）

- **目标**：把执行面攻击面降到可控范围
- **范围**：目录/命令/网络/提权/文件读写策略；默认拒绝策略；可审计的拒绝原因
- **DoD**：策略拒绝与绕过测试覆盖

#### AG-PR-03：Tool/Skill 插件化（带沙箱）

- **依赖**：BE-PR-06（协议规范）
- **目标**：工具可扩展但不扩大风险面
- **范围**：tool manifest、参数校验、权限/审批策略映射、执行沙箱（超时/并发/路径）

#### AG-PR-04：服务化运行（Windows Service）+ 日志落盘规范

- **目标**：企业可部署、可运维
- **范围**：服务化/开机自启；日志结构化与轮转；配置文件标准位置

#### AG-PR-05：自动更新/回滚（签名校验）

- **依赖**：BE-PR-03（审计/证明）、BE-PR-06（发布元数据规范）
- **目标**：安全分发，防供应链劫持
- **范围**：更新元数据签名、包签名校验、灰度、断电回滚

---

### 3.2.3 前端 PR（Web Console + Android）

#### FE-PR-01：Web 控制台 MVP（只读可观测）

- **依赖**：现有 OpenAPI + events/artifacts
- **目标**：企业运营/排障入口
- **范围**：任务列表/详情、事件流、artifacts 展示、节点在线列表

#### FE-PR-02：审批与审计 UI（强绑定上下文展示）

- **依赖**：BE-PR-01（RBAC）、BE-PR-03（审计）、BE-PR-06（上下文字段规范）
- **目标**：审批可解释、可追溯、可核对
- **范围**：审批卡片展示 command/cwd/runId/风险原因；审批操作与审计查看

#### FE-PR-03：断线恢复与补流（lastSeq）

- **依赖**：已支持 `lastSeq`
- **目标**：弱网/断线可恢复事件流
- **范围**：WebSocket 断线重连；按 lastSeq 补历史；去重与顺序保证

#### FE-PR-04：Android 客户端（语音入口 + 审批）

- **依赖**：BE-PR-01（身份）、BE-PR-06（协议）
- **目标**：移动端可发起任务、实时查看、审批
- **范围**：语音输入、任务创建、订阅事件、审批交互、日志/变更摘要

#### FE-PR-05：企业级账号体系与多租户（可选）

- **依赖**：BE-PR-01（RBAC/资源级授权）
- **目标**：企业内部组织结构落地（项目/团队/空间）
- **范围**：组织/项目管理 UI、成员管理、权限配置

---

## 3.3（保留）原始 PR 列表（便于对照）

### PR-01：领域层抽取（Domain First）

- **目标**：把 `TaskService` 中的状态机/审批绑定/事件规范化逻辑抽到领域层（减少 Spring/JPA 侵入）
- **范围**
  - `control-plane-spring`：新增 `domain` 包，提取 Task 状态机与校验器
  - `TaskService` 变为“编排+持久化调用”
- **DoD**
  - 现有集成测试全部通过
  - 关键规则（审批上下文一致性、lease claim）具备单元测试
- **回滚**：仅结构重构，不改变 API/DB

### PR-02：lane 串行调度升级（避免 re-enqueue 抖动）

- **目标**：从“取到不匹配就重新入队”的策略，升级为可控调度（减少 busy loop 与队列抖动）
- **方案**
  - 引入“候选集合/优先队列”或“按 profile 分队列”
  - lane（`sessionKey`）使用 DB 查询/锁或单独的 lane 调度器
- **DoD**
  - 在高并发下 profile 命中率稳定
  - lane 串行严格成立（同 key 不并发执行）

### PR-03：队列语义标准化（MQ 抽象完善）

- **目标**：统一 queue backend 的语义：可见性超时/ack/nack（为 Kafka/Rabbit 做准备）
- **范围**
  - `TaskQueuePort` 扩展：`enqueue / poll(lease) / ack / nack / requeue`
  - Redis/Rabbit/InMem 适配器对齐行为
- **DoD**
  - lease 到期可再投递
  - 端到端“至少一次”语义文档化并通过测试

### PR-04：安全基线 v1（TLS + JWT/RBAC）

- **目标**：用企业可接受的身份体系替代单 token：JWT（短期）+ RBAC（Operator/Viewer/Admin）+ agent 身份
- **范围**
  - `control-plane-spring`：Spring Security 配置、JWT 签发/校验、角色授权
  - `pc-agent-java`：client 使用 agent JWT 或 mTLS client cert
- **数据**
  - 新增 `users/roles/credentials` 表（Flyway）
- **DoD**
  - 现有 operator/agent token 模式保留为 dev profile（可关闭）
  - 所有 API 都有权限覆盖测试

### PR-05：mTLS（Agent ↔ Control Plane）

- **目标**：Agent 连接必须可选启用 mTLS；企业内网部署可强制开启
- **范围**
  - Control Plane：配置 server TLS + client cert 校验
  - Agent：OkHttp 配置 client cert、CA pinning（可选）
- **DoD**
  - TLS on/off 可通过 profile 切换
  - 文档 + 示例证书生成脚本

### PR-06：审计不可篡改（WORM/签名链）

- **目标**：审计日志具备完整性校验（hash chain 或签名），支持归档导出
- **方案**
  - audit_log 增加 `prev_hash / hash / signature`（或独立 audit table）
  - 定期归档到对象存储/文件（先本地文件适配器）
- **DoD**
  - 任意篡改可被检测
  - 可导出某 task 的审计证明包

### PR-07：可观测性 v1（结构化日志 + 指标 + OTel）

- **目标**：企业运维必需：指标、追踪、统一 traceId 贯穿
- **范围**
  - Control Plane：Micrometer + Prometheus endpoint、关键计数/延迟直方图
  - Agent：结构化日志（JSON）、关键耗时指标
  - 全链路：traceId/runId 规范化（写入事件顶层字段或固定 payload schema）
- **DoD**
  - Grafana dashboard（最小版本）
  - 关键告警规则样例

### PR-08：Tool/Skill 插件化（生产可扩展，带安全沙箱）

- **目标**：Tool schema/权限/审批策略统一；支持按 profile 启用不同 tool 集
- **范围**
  - Agent：tool manifest、版本、参数校验、执行沙箱（最小）
  - Control Plane：tool catalog（可选）用于 UI 展示与审批上下文
- **DoD**
  - 现有 `command.exec` 仍可用
  - 新增至少 1 个 tool（如 `git.status`）验证扩展机制
  - 新增至少 1 条“策略拒绝/审批强绑定绕过”测试用例

### PR-09：Agent 服务化 + 安装包（Windows 优先）

- **目标**：企业可部署：后台服务运行、开机自启、日志落盘、配置文件
- **范围**
  - `jpackage` 产物（msi/exe）
  - Windows Service wrapper（可选先用 NSSM 或 WinSW）
- **DoD**
  - 文档：安装/卸载/升级/回滚
  - 崩溃自恢复

### PR-10：自动更新/回滚（安全分发）

- **目标**：Agent 可安全更新：签名校验、灰度、回滚
- **范围**
  - Control Plane：发布元数据与下载地址（可先静态文件）
  - Agent：更新检查、下载、校验、切换、回滚
- **DoD**
  - 断电/失败可回滚到上一版本

---

## 4. 验收标准（企业级 DoD 总表）

- **安全**：TLS/mTLS 可用；RBAC；token 可轮换与吊销；审批不可绕过；审计可校验
- **可靠性**：至少一次语义清晰；任务不丢；重启/断线可恢复；lane 串行成立
- **可观测**：指标/日志/追踪齐全；能定位一次任务的全链路 runId
- **交付**：Agent 可服务化部署；可升级回滚；配置可热更新
- **契约**：OpenAPI + 契约测试覆盖关键路径；事件 schema 版本化策略明确

---

## 5. 研发协作与 PR 规范（建议）

- **每个 PR 控制规模**：可在 1~2 天内完成并可回滚
- **强制门禁**：
  - `mvn test` 必过
  - Flyway migration 必带（涉及 DB）
  - OpenAPI 契约测试必更新（涉及 API）
- **提交内容结构**
  - `## Summary`（为什么做）
  - `## Changes`（涉及模块/文件）
  - `## Test plan`（如何验证）
  - `## Rollback`（如何回滚）
