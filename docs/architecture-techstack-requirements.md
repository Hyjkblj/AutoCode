# 架构技术栈明确需求（Java 版）

## 1. 文档目标
本文件用于定义项目的**硬性技术栈要求**与**架构落地边界**，作为研发、测试、运维统一执行标准。

- 项目代号：`MobileVoice-CodeOps`
- 适用阶段：`MVP -> V1.0`
- 文档属性：`技术基线（必须遵守）`

---

## 2. 总体约束（硬性）

## 2.1 技术路线
1. 后端与 PC Agent **必须使用 Java** 实现。
2. 移动端首发 **必须为 Android（Java）**。
3. 架构必须支持多助手（Codex / Claude Code）并通过统一适配层对接。

## 2.2 产品能力边界
1. 必须支持语音输入 -> 任务执行 -> 实时回传 -> 审批 -> 完成闭环。
2. 必须支持任务级审计追踪（谁在何时批准了什么操作）。
3. 必须支持弱网断线恢复（事件续流）。

---

## 3. 分层架构要求

## 3.1 客户端层（Android）
1. 必须提供语音输入与文本修正。
2. 必须支持任务实时状态流展示（WebSocket）。
3. 必须支持审批卡片（批准/拒绝）。
4. 必须支持查看日志与变更摘要。

## 3.2 控制平面（Cloud Control Plane）
1. 必须提供统一入口：REST + WebSocket。
2. 必须实现任务状态机与审批流。
3. 必须实现统一事件总线与事件持久化。
4. 必须实现节点注册、心跳、任务路由。

## 3.3 执行层（PC Node Agent）
1. 必须以守护进程形式运行。
2. 必须支持多助手适配器（至少 Codex 一个生产可用）。
3. 必须执行目录白名单与命令风险控制。
4. 必须上报结构化事件。

---

## 4. 技术栈基线（明确版本）

## 4.1 Android（移动端）
1. 语言：`Java 17`（Android Gradle Toolchain）
2. 最低系统：`Android 10 (API 29)`
3. 网络：`OkHttp 4.x`（HTTP + WebSocket）
4. 语音：`SpeechRecognizer + RecognizerIntent`
5. 本地存储：`Room 2.6+`
6. JSON：`Moshi 或 Gson（二选一并全局统一）`

## 4.2 后端（控制平面）
1. 语言运行时：`Java 21 LTS`
2. 框架：`Spring Boot 3.5.x`
3. 安全：`Spring Security 6.x + JWT`
4. 实时通信：`Spring WebSocket (STOMP)` 或原生 WS（二选一）
5. 数据库：`MySQL 8.4 LTS`
6. 缓存/流：`Redis 7`
7. 数据访问：`Spring Data JPA + Flyway`
8. 构建：`Maven 3.9+`

## 4.3 PC Node Agent
1. 语言运行时：`Java 21 LTS`
2. 进程管理：`ProcessBuilder`
3. 网络：`OkHttp WebSocket Client`
4. 序列化：与后端同一 JSON 库（禁止混用）
5. 打包：`jlink/jpackage` 或 fat-jar（二选一）

## 4.4 可观测性与运维
1. 指标：`Micrometer + Prometheus`
2. 健康检查：`Spring Boot Actuator`
3. 日志：`JSON 结构化日志（logback）`
4. 可视化：`Grafana`
5. 追踪：`OpenTelemetry (OTLP)`（V1.0 必须）

## 4.5 部署基线
1. 容器化：`Docker`
2. 编排：`Kubernetes`（生产必须）
3. 配置管理：`环境变量 + Secret Manager`
4. 证书：`TLS`，节点连接建议 `mTLS`

---

## 5. 协议与接口要求

## 5.1 通信协议
1. 必须采用统一消息模型：`req / res / event`。
2. 首帧必须握手认证（connect + token + deviceId）。
3. 副作用操作必须携带 `idempotencyKey`。

## 5.2 REST 最小集合
1. `POST /api/v1/tasks`：创建任务
2. `GET /api/v1/tasks/{taskId}`：查询任务
3. `POST /api/v1/tasks/{taskId}/approval`：审批
4. `POST /api/v1/tasks/{taskId}/cancel`：取消
5. `GET /api/v1/tasks/{taskId}/events`：历史事件

## 5.3 WebSocket 最小集合
1. `/ws` 建连
2. `/topic/tasks/{taskId}` 订阅
3. 支持 `lastEventId` 断线恢复

---

## 6. 统一事件模型要求

事件字段必须包含：
1. `eventId`
2. `taskId`
3. `sessionId`
4. `assistant`
5. `type`
6. `timestamp`
7. `payload`

事件类型最小集：
1. `task_started`
2. `assistant_output`
3. `tool_start`
4. `tool_end`
5. `file_patch_preview`
6. `approval_required`
7. `approval_result`
8. `task_done`
9. `task_failed`

---

## 7. 安全与合规要求（硬性）

1. 必须启用 TLS 传输。
2. 必须实现 RBAC（至少 Admin / Operator / Viewer）。
3. 必须实现工作区目录白名单。
4. 高风险动作（exec、git push、外网写）必须审批。
5. 审批必须记录审计日志（操作人、时间、上下文）。
6. Token 必须短期有效并支持吊销。

---

## 8. 性能与可靠性 SLO

1. 任务创建接口延迟：P95 < `300ms`
2. 事件推送端到端延迟：P95 < `800ms`
3. 网关可用性：月度 >= `99.9%`
4. 节点心跳超时：`30s` 判定离线
5. 断线恢复窗口：至少支持最近 `30min` 事件补偿

---

## 9. 开发规范与工程要求

1. 必须统一代码风格与格式化规则（Checkstyle/Spotless）。
2. 必须开启静态扫描（SpotBugs + Dependency Check）。
3. 所有 DB 变更必须通过 Flyway migration。
4. 所有接口必须有 OpenAPI 文档。
5. 所有事件 schema 必须版本化（`eventVersion`）。

---

## 10. 测试要求（发布门禁）

## 10.1 后端
1. 单元测试覆盖率（核心模块）>= `70%`
2. 状态机、审批、幂等逻辑必须有集成测试
3. WebSocket 重连续流必须有自动化测试

## 10.2 Agent
1. 进程异常恢复测试必须通过
2. 白名单/高风险拦截测试必须通过
3. 适配器协议解析回归测试必须通过

## 10.3 移动端
1. 语音识别失败与弱网重连场景必须覆盖
2. 审批交互主路径必须有 UI 自动化用例

---

## 11. 里程碑交付要求

## M1（第 2 周）
1. 网关握手 + 任务创建 + 节点心跳跑通

## M2（第 4 周）
1. Codex 任务执行与事件回传跑通
2. Android 可实时查看日志流

## M3（第 6 周）
1. 审批流 + 安全白名单 + 审计落库上线

## M4（第 8 周）
1. Claude 适配接入
2. 统一事件模型稳定

## M5（第 10-12 周）
1. 性能压测达标
2. 灰度发布与回滚预案完成

---

## 12. 验收清单（DoD）

1. Android 端可语音发起任务并看到完成结果。
2. 至少支持 1 个助手生产可用（Codex）。
3. 高风险操作必须走审批并可审计追溯。
4. 断网重连后可恢复任务事件流。
5. 压测达到 SLO 指标。
6. 安全扫描与依赖漏洞门禁通过。

---

## 13. 推荐目录结构

```text
docs/
  architecture-techstack-requirements.md
mobile-android-java/
control-plane-spring/
pc-agent-java/
infra/
```

---

## 14. 一句话结论
本需求文档定义了一个**Java 主栈、可审计、可扩展、可上线**的技术基线；任何实现方案不得低于本文件的 MUST 级要求。
