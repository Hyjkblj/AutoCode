# AutoCode 后端生成方案（现状对齐版）

更新时间：2026-04-29  
版本：V1.1  
状态：可执行草案（基于当前仓库真实状态）

---

## 1. 文档目标与依据

本方案不是理想化重写方案，而是基于当前代码仓库现状，给出后端生成能力的最短升级路径。

依据文档：

1. `docs/升级2.0/智能体设计评分.md`
2. `docs/升级2.0/架构评分.md`
3. `docs/升级2.0/backend-upgrade-master-plan-2026-04.md`
4. `docs/升级2.0/fullstack-generation-solution.md`
5. `docs/升级2.0/langchain-langgraph-agent-upgrade-plan-2026-04.md`

现状核查范围：

1. `python-agent`
2. `control-plane-spring`
3. `shared-protocol`

---

## 2. 当前系统真实状态（已落地能力）

### 2.1 控制面（Java）已具备

1. 任务创建幂等：`Idempotency-Key` + `idempotency_records` 映射已实现。
2. 任务租约与回收：`TaskEntity` 包含 `leasedAt/leaseExpiresAt/retryCount`，并有定时回收逻辑。
3. 队列 ACK/NACK：`TaskQueuePort` 与 `RedisBackedTaskQueue` 已支持 ack/nack。
4. 事件去重与顺序：按 `eventId` 去重，`task.nextSeq` 分配 seq，且 `task_events(task_id, seq_num)` 有唯一约束。
5. 协议契约体系：`shared-protocol` 包含事件 schema、示例、校验器与测试。

### 2.2 Python Agent 已具备

1. 多智能体主干：`Intent/Planner/Coder/Reviewer/Tester/Orchestrator`。
2. DAG 并行：`review || test` 并行执行（`DagScheduler`）。
3. 记忆层：`RedisMemory` 支持 Redis 与本地内存 fallback。
4. Web 生成路径：`CoderAgent + WebTemplateGenerator` 可生成静态前端并打包 `export.zip`。
5. Artifact 上传：`ControlPlaneClient.upload_artifact` 已接入控制面上传接口。

### 2.3 工程现状（客观）

1. 控制面 Java 文件：`86`，测试：`18`。
2. Python 主代码文件：`26`，测试：`16`。
3. `python-agent/requirements.txt` 当前仅 `redis`，依赖声明明显不足。
4. 仓库无 `.github/workflows`，CI 门禁尚未落地。

---

## 3. 当前关键缺口（后端生成相关）

### 3.1 生成能力缺口

1. `CoderAgent` 当前“生成项目”只走 `target=web`，产物是 `index.html/styles.css/app.js/README.generated.md`。
2. 尚未具备“真实后端应用生成”（API、数据库模型、运行脚本、后端依赖）。
3. 生成后缺少后端可运行验证门禁（只验证静态文件链路）。

### 3.2 Python 侧可靠性缺口

1. `BaseAgent.publish_event` 直接调用 `client.publish_event`，无 ACK 判定、无重试、无 outbox。
2. Python 事件 seq 在内存字典中，进程重启后会重置。
3. Python 侧无分布式锁，存在多实例重复执行风险。
4. `IntentAgent` 仍以关键词规则为主，复杂意图识别不稳定。
5. 无熔断器与整体超时预算；`except Exception` 使用较多。

### 3.3 交付治理缺口

1. 缺少 CI 自动化质量门禁。
2. 覆盖率目标未工具化约束（Java JaCoCo / Python coverage）。
3. 依赖与配置治理不足，影响生成链路稳定性。

---

## 4. 方案定位（现状对齐）

### 4.1 不重做的部分（沿用）

1. 保留 `Java Control Plane` 的任务、审计、协议与安全中枢角色。
2. 保留现有 Agent 主干与 DAG 框架。
3. 保留控制面已有的幂等、租约、队列 ack/nack 能力。

### 4.2 必须新增的部分（补齐）

1. 在 Python 侧补齐“后端生成能力链路”。
2. 在 Python 侧补齐“可靠事件发布与执行互斥”。
3. 建立后端生成质量门禁与 CI。

### 4.3 迁移策略

1. 先在 `legacy orchestrator` 完成后端生成闭环。
2. 再迁移到 `LangGraph` 编排内核，采用双引擎灰度。

---

## 5. 目标后端生成能力（定义）

后端生成任务完成后，最小可交付标准：

1. 生成真实后端代码（至少 Flask/FastAPI + SQLite）。
2. 提供可调用 CRUD API（非 mock）。
3. 生成运行说明与依赖文件（`requirements.txt`、`README`）。
4. 通过自动验证（语法、路由、数据层、启动检查）。
5. 能作为 artifact 上传并通过现有事件链路回传。

---

## 6. 架构设计（基于现状）

```text
Control Plane (existing)
  -> Task create/poll/lease/idempotency/event ingest (existing)

Python Agent Runtime (upgrade)
  -> Orchestrator (legacy first, langgraph later)
  -> Intent/Planner (LLM+fallback)
  -> Backend Generation Pipeline (new)
      RequirementAnalyzer
      ModelSchemaGenerator
      ApiGenerator
      ValidationGate
      FixLoop
  -> Reviewer || Tester (existing enhanced)
  -> Artifact Publish (existing)
  -> Reliable Event Publish (new: ack/retry/outbox-lite)
```

---

## 7. 详细实施方案

## 7.1 P0（先做，2-4周）

### P0-1 新增后端生成链路（最小可用）

目标：在现有 `CoderAgent` 中增加 `target=backend|fullstack` 的真实后端生成能力。

改造点：

1. 新增 `python-agent/generators/backend_generator.py`。
2. 扩展 `python-agent/agents/coder_agent.py` 的路由逻辑。
3. 生成文件最小集合：
   - `backend/app.py`
   - `backend/models.py`（或内嵌模型）
   - `requirements.txt`
   - `README.generated.md`
4. 沿用现有 artifact 打包与上传机制。

验收：

1. 输入“待办/博客/用户管理”等需求，可生成可运行后端。
2. 本地命令可启动并返回基础 API 响应。

### P0-2 生成结果验证门禁 + Fix Loop

目标：避免“生成成功但不可运行”。

改造点：

1. 新增 `python-agent/generators/validation_gate.py`。
2. 校验项：
   - 必需文件存在
   - API 路由存在
   - DB 初始化逻辑存在
   - 关键命令可执行
3. 在 `agent_orchestrator.py` 增加 Fix Loop（最多3轮）。

验收：

1. 失败时自动回修并记录失败原因。
2. 输出 `TASK_FAILED` 包含明确 error/reason。

### P0-3 Python 事件可靠投递增强

目标：补齐 Python 到控制面的可靠语义。

改造点：

1. 改造 `python-agent/agents/base_agent.py`：`publish_event_with_retry`。
2. 改造 `python-agent/client/control_plane_client.py`：标准化回包校验与重试策略。
3. 增加轻量 outbox（本地内存/Redis 可选）以应对瞬时失败。

验收：

1. 控制面短时不可达后恢复，事件最终可达。
2. 不出现同一业务事件重复副作用。

### P0-4 Python 分布式互斥与超时治理

目标：防止重复执行与长尾阻塞。

改造点：

1. 新增 `python-agent/orchestrator/distributed_lock.py`（Redis `SET NX EX` + Lua 解锁）。
2. 在 `agent_orchestrator.py` 的 `handle_task` 外围加任务互斥。
3. 新增 `python-agent/utils/circuit_breaker.py` 并接入 Planner/Reviewer/生成链路。
4. 增加阶段级超时预算。

验收：

1. 双实例抢同一任务仅一实例执行。
2. LLM 持续异常时自动熔断并回退。

---

## 7.2 P1（再做，4-6周）

### P1-1 Intent 升级为 LLM 主判定 + 规则兜底

现状：`intent_agent.py` 关键词规则为主。  
目标：复杂需求意图识别更稳定。

改造点：

1. 引入结构化意图输出（`intent/confidence/reason`）。
2. LLM 不可用时沿用当前规则路径。

### P1-2 LangGraph 分阶段接管

顺序：

1. `analyze/test`
2. `code_change`
3. `backend/fullstack generation`
4. `deploy`

要求：

1. 保留 `AGENT_ENGINE=legacy|langgraph`。
2. 双写比对输出一致性。

### P1-3 可观测性补齐

改造点：

1. trace 覆盖 `handle_task -> generate -> validate -> publish`。
2. 指标新增：生成成功率、Fix Loop 成功率、事件重试次数。

---

## 7.3 P2（优化，持续）

1. LLM 响应缓存（LRU/TTL）。
2. 插件化生成器（多技术栈模板）。
3. API Gateway、告警体系、性能压测体系完善。

---

## 8. 数据契约与状态约束

### 8.1 任务状态

`PENDING/QUEUED -> LEASED/RUNNING -> SUCCEEDED|FAILED|CANCELED`

说明：控制面已有租约语义，Python 侧新增锁只负责“本侧互斥防重”。

### 8.2 事件契约增强建议

当前控制面 `ingestEvent` 返回 `ApiResponse<TaskSummary>`，可作为“已接收”语义。  
建议新增可选 ACK 字段（向后兼容）：

1. `ack`
2. `acceptedSeq`
3. `duplicate`
4. `errorCode`

---

## 9. 里程碑与时间线（对齐现有计划）

1. 阶段0（2026-05-04 ~ 2026-05-17）：基线、开关、最小 CI。
2. 阶段1（2026-05-18 ~ 2026-05-31）：后端生成最小链路 + 验证门禁。
3. 阶段2（2026-06-01 ~ 2026-06-14）：可靠投递、分布式锁、熔断超时。
4. 阶段3（2026-06-15 ~ 2026-06-28）：LangGraph 低风险迁移与灰度。
5. 阶段4（2026-06-29 ~ 2026-07-12）：核心链路迁移与可观测性完善。
6. 阶段5（2026-07-13 ~ 2026-07-26）：全量评估、收敛、运行手册。

---

## 10. 验收指标（后端生成专项）

1. 后端生成任务成功率：不低于当前基线且提升 `>=2%`。
2. 可运行率：生成产物可直接启动比例 `>=90%`。
3. 可靠性：事件丢失率 `<0.01%`，重复执行率 `<0.1%`。
4. 性能：核心链路 P95 下降 `>=20%`。
5. 工程质量：Java/Python 核心覆盖率阶段目标 `>=70%`。

---

## 11. 风险与对策（现状相关）

1. 风险：Python 依赖声明不足导致运行不一致。  
对策：补全 `requirements.txt` 并锁版本。
2. 风险：当前无 CI，质量靠人工。  
对策：建立 `mvn test + pytest + lint` 强制门禁。
3. 风险：后端生成首次接入波动大。  
对策：先单栈（Flask+SQLite）收敛，再扩栈。
4. 风险：Python 事件发布无重试可能丢事件。  
对策：优先实现重试与 outbox-lite。

---

## 12. 立即执行清单（两周）

1. 创建 `backend_generator.py`，先支持 Flask+SQLite。
2. 在 `CoderAgent` 增加 `target=backend|fullstack` 路由。
3. 创建 `validation_gate.py` 并接入 orchestrator。
4. 在 `BaseAgent` 增加事件重试发布能力。
5. 新增 `distributed_lock.py`，在 `handle_task` 外围接入。
6. 新增 `circuit_breaker.py`，先接 Planner/Reviewer。
7. 新建 CI 工作流（Java + Python 测试门禁）。

---

## 13. 最终建议

1. 当前系统不是“从零开始”，而是“控制面较强、Python 侧生成与可靠性待补齐”。
2. 后端生成升级应优先补齐 Python 侧缺口，而不是重做控制面能力。
3. 路线应是：先把 `backend generation + validation + reliability` 做实，再推进 LangGraph 编排迁移。

一句话：基于现有底座做增量升级，先把“能稳定生成可运行后端”这件事闭环。
