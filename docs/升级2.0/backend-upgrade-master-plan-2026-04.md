# AutoCode 后端升级总方案（Master Plan）

更新时间：2026-04-29  
版本：V1.0  
适用范围：`control-plane-spring` + `python-agent` + 共享协议/部署链路

---

## 1. 方案目标

本方案用于统一 AutoCode 后端升级路径，聚焦三件事：

1. **先稳**：可靠性与一致性达生产级。  
2. **再迁**：以 LangGraph + LangChain 渐进升级编排内核。  
3. **再优**：性能、可观测性、运维成熟度全面提升。  

目标结果：

1. 后端综合能力从当前 `B+ / A-` 提升到 `A / A+`。  
2. 支持可灰度、可回滚、可审计、可扩展的生产运行模式。  

---

## 2. 升级范围与边界

## 2.1 包含范围

1. 任务编排与执行链路（Intent/Planner/Coder/Reviewer/Tester/Orchestrator）。
2. 事件通信与控制面协议（ACK、幂等、重试、序列一致性）。
3. 任务状态与分布式协调（锁、租约、状态机）。
4. LLM 调用治理（结构化输出、熔断、超时、降级）。
5. 可观测性与性能治理（日志、指标、追踪、压测）。
6. 工程保障（测试覆盖、CI/CD、依赖治理）。

## 2.2 不在本轮范围

1. 全量重写控制面或完全替换事件模型。
2. 一次性迁移到“纯 LangChain Agent 黑盒”。
3. 非核心业务的大规模前端改造。

---

## 3. 当前问题基线（后端）

1. 事件发布仍偏 fire-and-forget，存在丢失/重复风险。  
2. 多实例任务执行缺少强一致协调（锁/租约不足）。  
3. LLM 失败治理不完整（熔断、预算、异常边界待强化）。  
4. 同步阻塞较多，P95 时延与吞吐有瓶颈。  
5. 可观测性覆盖不足，故障定位成本高。  
6. 工程能力短板明显（测试覆盖、CI/CD、依赖管理）。  

---

## 4. 总体架构策略

## 4.1 技术路线

1. **LangGraph**：作为 Python Agent 的执行内核（状态机 + 节点编排）。  
2. **LangChain**：作为能力层（模型适配、Tool 接口、Prompt/结构化输出）。  
3. **现有 Control Plane**：继续作为任务分发、审计、安全与事件中枢。  

## 4.2 升级原则

1. 增量升级，不全量重写。  
2. 双引擎并行（`legacy | langgraph`）保障回退。  
3. 指标驱动上线，未达门槛不放量。  
4. 默认失败安全，所有失败可观测、可追溯、可恢复。  

---

## 5. 目标后端拓扑

```text
Control Plane (Java)
  -> Task Dispatch / Lease
  -> Event ACK / Idempotency / Audit
  -> Policy & Approval

Python Agent Runtime
  -> Engine Router (legacy | langgraph)
  -> LangGraph State Machine
      Intent Node (LLM + heuristic fallback)
      Planner Node (structured output)
      Coder Node
      Parallel Nodes (Reviewer || Tester)
      Merge/Publish Node
  -> Reliability Layer (lock/lease/retry/circuit breaker)
  -> Memory Layer (Redis primary + local fallback)
  -> Observability Layer (OTel + metrics + structured logs)
```

---

## 6. 按优先级的升级任务包

## 🔴 P0（必须先做，2026-05-04 ~ 2026-06-14）

### P0-1 事件可靠投递闭环

目标：

1. 引入 ACK 语义、重试机制、幂等去重。  
2. 可选 Outbox 保障进程异常下不丢事件。  

关键改造：

1. `python-agent/agents/base_agent.py`  
2. `python-agent/client/control_plane_client.py`  
3. `control-plane-spring` 事件接收 ACK 与去重逻辑  

验收：

1. 控制面短时不可用后恢复，事件最终可达率 `>=99.9%`。  
2. 重复投递不产生重复业务效果。  

### P0-2 分布式锁 + 任务租约

目标：

1. 同一 `taskId` 仅一个执行者。  
2. 异常退出自动释放，长任务可续租。  

关键改造：

1. `python-agent/orchestrator/agent_orchestrator.py`  
2. 新增 `python-agent/orchestrator/distributed_lock.py`  
3. 控制面/存储层补租约状态字段  

验收：

1. 双实例并发抢单无重复执行。  
2. 锁误删与死锁场景可被测试覆盖。  

### P0-3 LLM 熔断 + 超时预算 + 异常分层

目标：

1. 失败快速熔断，自动降级 fallback。  
2. 明确异常边界，避免吞掉系统级异常。  

关键改造：

1. `python-agent/agents/planner_agent.py`  
2. `python-agent/agents/reviewer_agent.py`  
3. 新增 `python-agent/utils/circuit_breaker.py`  
4. 定义 `AgentError/LLMError/SandboxError/ValidationError`  

验收：

1. 连续失败场景中调用量显著下降。  
2. 错误码与日志可直接定位失败节点。  

### P0-4 双引擎开关 + 基线测试 + CI/CD 最小闭环

目标：

1. 支持 `AGENT_ENGINE=legacy|langgraph`。  
2. 建立后端回归与发布前自动校验链。  

关键改造：

1. `python-agent/orchestrator/agent_orchestrator.py` 引擎路由  
2. Python/Java 核心链路测试补齐  
3. CI 执行 `mvn test` + `pytest` + 基础静态检查  

验收：

1. 任意版本可一键回退 legacy。  
2. PR 合入前必须通过自动测试门禁。  

---

## 🟡 P1（应该改进，2026-06-15 ~ 2026-07-26）

### P1-1 LangGraph 分阶段迁移

顺序：

1. `analyze/test`。  
2. `code_change`（含 reviewer/tester 并行节点）。  
3. `deploy`（含审批节点）。  

验收：

1. 与 legacy 双写比对，业务结果一致率达标。  
2. 灰度阶段异常率不高于基线。  

### P1-2 全链路可观测性

目标：

1. Trace 覆盖编排主路径。  
2. Metrics 包含成功率、失败率、P95、重试、熔断状态。  
3. 结构化日志统一字段标准。  

验收：

1. 关键链路 span 覆盖率 `>=95%`。  
2. 生产故障 MTTR 显著下降。  

### P1-3 异步化关键路径 + 性能治理

目标：

1. 并行化 LLM 与上下文读取。  
2. 完善数据库连接池与压测体系。  

验收：

1. P95 时延下降 `>=20%`。  
2. 高并发吞吐提升（目标 `~2x`，以压测为准）。  

---

## 🟢 P2（可以优化，2026-07-27 之后）

### P2-1 LLM 响应缓存（LRU/TTL）

1. 降低重复请求成本与时延。  
2. 命中率、绕过率、失效率可观测。  

### P2-2 插件化 Agent 扩展

1. 动态装载 `*_agent.py`。  
2. 插件白名单与隔离策略。  

### P2-3 平台化增强

1. API Gateway 统一入口。  
2. 告警与运行手册完善（Prometheus/Grafana/AlertManager）。  
3. ADR、故障排查、性能调优文档体系。  

---

## 7. 关键时间线（固定日期）

1. **阶段0（基线与开关）**：2026-05-04 ~ 2026-05-17  
2. **阶段1（能力层接入）**：2026-05-18 ~ 2026-05-31  
3. **阶段2（低风险链路迁移）**：2026-06-01 ~ 2026-06-14  
4. **阶段3（核心链路迁移）**：2026-06-15 ~ 2026-06-28  
5. **阶段4（高风险链路治理）**：2026-06-29 ~ 2026-07-12  
6. **阶段5（全量评估收敛）**：2026-07-13 ~ 2026-07-26  

---

## 8. 验收指标（上线门槛）

1. 任务成功率：不低于基线且提升 `>=2%`。  
2. 可靠性：事件丢失率 `<0.01%`，重复执行率 `<0.1%`。  
3. 性能：后端链路 P95 下降 `>=20%`。  
4. 稳定性：结构化解析错误率下降 `>=70%`。  
5. 可观测性：关键 trace 覆盖率 `>=95%`。  
6. 工程质量：核心后端测试覆盖率提升到 `>=70%`（阶段目标）。  

---

## 9. 灰度与回滚策略

## 9.1 灰度策略

1. 按意图灰度：`LANGGRAPH_INTENTS=analyze,test,...`  
2. 按流量灰度：`5% -> 20% -> 50% -> 100%`  
3. 按租户灰度：白名单项目先行  

## 9.2 回滚触发条件

满足任一条件立即回切 `legacy`：

1. 成功率下降超过 `1%`。  
2. P95 上升超过 `20%`。  
3. 重复执行率超过 `0.1%`。  
4. 事件丢失率超过 `0.01%`。  

---

## 10. 风险与对策

1. 依赖版本波动风险  
对策：锁定版本、月度统一升级窗口、自动回归。  
2. 迁移语义偏差风险  
对策：legacy 与 langgraph 双写比对。  
3. 性能回退风险  
对策：异步化、缓存、超时预算、压测前置。  
4. 团队认知成本风险  
对策：统一模板、节点开发规范、代码走查清单。  

---

## 11. 交付物清单

1. 后端升级设计包（本文件 + 状态机 + 事件契约）。  
2. 引擎开关与灰度发布 SOP。  
3. 可靠性增强实现（ACK/幂等/锁/租约/熔断）。  
4. LangGraph 迁移实现与双写比对报告。  
5. 可观测性看板与告警规则。  
6. 测试与 CI/CD 门禁配置。  

---

## 12. 最终决策建议

1. 立即启动 P0（可靠性与工程门禁），这是后端升级成败关键。  
2. LangChain/LangGraph 采用“能力层 + 编排内核”定位，不替代控制面核心职责。  
3. 任何迁移以灰度和回滚能力为前提，不满足门槛不放量。  

**一句话策略：先稳住后端底盘，再迁移编排内核，最后做性能与生态扩展。**

