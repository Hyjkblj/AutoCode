# AutoCode 智能体架构升级方案（LangChain + LangGraph）

更新时间：2026-04-29  
版本：V1.0  
状态：可执行草案（可直接进入评审）

---

## 1. 背景与结论

当前 AutoCode 已具备较好的多智能体基础（Intent/Planner/Coder/Reviewer/Tester + DAG + 事件驱动），但在以下方面存在升级空间：

1. 复杂意图理解与结构化输出稳定性。
2. 分布式可靠性（事件 ACK、重试、幂等、任务租约）。
3. 运维可观测性与故障定位效率。
4. 同步阻塞路径导致的高延迟与吞吐瓶颈。

结论：**采用“LangGraph 作为执行内核 + LangChain 作为能力层”的渐进式升级方案是合理且推荐的。**  
不建议全量重写为纯 LangChain Agent。

---

## 2. 升级目标

## 2.1 业务目标

1. 复杂任务成功率提升，减少误判与反复重试。
2. 降低端到端响应时延，提升并发吞吐能力。
3. 建立可灰度、可回滚、可观测的生产级智能体平台。

## 2.2 工程目标

1. 保留现有控制面与事件协议，不推倒重来。
2. 升级 Python Agent 编排内核到 LangGraph。
3. 使用结构化输出替代自由文本协议。
4. 强化容错机制：熔断、超时、重试、降级。

---

## 3. 架构策略

## 3.1 选型定位

1. `LangGraph`：负责状态机、节点编排、可恢复执行、HITL 插入点。
2. `LangChain`：负责模型统一接口、Tool 适配、Prompt 模板、结构化输出。
3. `现有系统`：继续承担 Control Plane、事件总线、业务协议、权限与审计。

## 3.2 设计原则

1. 渐进式迁移，按链路灰度，不一次性替换。
2. 双引擎并存，任何阶段都可快速回退到 legacy。
3. 指标先行，所有上线决策以 SLO/KPI 为门槛。
4. 默认失败安全，异常可定位、可恢复、可重放。

---

## 4. 目标架构（V2）

```text
Java Control Plane
  -> Task Dispatch
  -> Event ACK / Idempotency / Audit

Python Agent Runtime
  -> Engine Router (legacy | langgraph)
  -> LangGraph State Machine
      Intent Node (LLM + Heuristic Fallback)
      Planner Node (Structured Output)
      Coder Node
      Parallel Nodes: Reviewer || Tester
      Merge Node (Decision + Artifact)
  -> Tool Adapter Layer (LangChain Tools + Existing Tools)
  -> Memory Layer (Redis + Local Fallback)
  -> Reliability Layer (Lease/Lock/Retry/Circuit Breaker)
  -> Observability Layer (Trace + Metrics + Structured Logs)
```

---

## 5. 模块升级映射（基于当前仓库）

1. 编排入口与双引擎路由  
`python-agent/orchestrator/agent_orchestrator.py`
2. 意图识别升级（LLM 主判定 + 规则兜底）  
`python-agent/agents/intent_agent.py`
3. 规划阶段结构化输出与熔断  
`python-agent/agents/planner_agent.py`
4. 统一 LLM 适配（超时、重试、fallback）  
`python-agent/llm/llm_client.py`
5. 内存层增强（项目级隔离 + 持久化一致性）  
`python-agent/memory/redis_memory.py`
6. 事件可靠投递（ACK/幂等/重试）  
`python-agent/agents/base_agent.py`  
`python-agent/client/control_plane_client.py`
7. 并行执行与依赖控制（保留并增强 DAG）  
`python-agent/orchestrator/dag_scheduler.py`

---

## 6. 核心能力设计

## 6.1 状态机与编排

建议状态：

1. `PENDING`
2. `LEASED`
3. `RUNNING`
4. `SUCCEEDED`
5. `FAILED`
6. `CANCELED`

约束：

1. 同一 `taskId` 在同一时刻仅一个执行者。
2. 状态迁移必须携带版本号与时间戳。
3. 中断恢复后可继续未完成节点，不重复已成功节点。

## 6.2 结构化输出

1. Intent 输出：`intent/confidence/reason`。
2. Planner 输出：`plan_name/steps/risk_level`。
3. Reviewer 输出：`approved/issues/summary`。
4. 全部通过 schema 校验，不合法即 fallback。

## 6.3 可靠性机制

1. 分布式锁：`SET NX EX` + Lua compare-and-del。
2. 任务租约：长任务 heartbeat 续租，避免锁误过期。
3. 事件 ACK：发布后确认，未确认指数退避重试。
4. 幂等键：`eventId + taskId + seq`，控制面去重。
5. 熔断器：失败阈值触发 OPEN，冷却后 HALF_OPEN 探测。

## 6.4 可观测性

1. Trace：覆盖 `handle_task -> intent -> plan -> execute -> publish`。
2. Metrics：成功率、失败率、P95、重试次数、熔断状态、队列积压。
3. Logs：结构化字段统一（taskId/runId/traceId/intent/planName/errorCode）。

---

## 7. 12 周实施计划（含具体日期）

## 阶段 0：基线与开关（2026-05-04 ~ 2026-05-17）

1. 建立基线指标：成功率、P50/P95、失败原因 TopN。
2. 新增引擎开关：`AGENT_ENGINE=legacy|langgraph`。
3. 增加回归测试模板与压测基线脚本。

交付物：

1. 基线报告。
2. 双引擎路由骨架。
3. 回滚操作手册 V1。

## 阶段 1：能力层接入（2026-05-18 ~ 2026-05-31）

1. 接入 LangChain 模型抽象与结构化输出。
2. 保持现有流程不变，仅替换调用层与解析层。
3. Planner/Intent 完成 schema 化。

交付物：

1. 可运行的结构化输出链路。
2. 解析失败自动 fallback。

## 阶段 2：低风险链路迁移（2026-06-01 ~ 2026-06-14）

1. `analyze`、`test` 迁移到 LangGraph。
2. 灰度 10% 流量，按项目白名单放量。

交付物：

1. LangGraph 子图 V1。
2. 灰度观测报表（日级）。

## 阶段 3：核心链路迁移（2026-06-15 ~ 2026-06-28）

1. `code_change` 迁移（Coder -> Reviewer || Tester）。
2. 引入并行节点收敛与失败分流策略。

交付物：

1. code_change 主链路在 LangGraph 可稳定执行。
2. 失败可追踪到节点级别。

## 阶段 4：高风险链路与治理（2026-06-29 ~ 2026-07-12）

1. `deploy` 迁移并加入审批节点。
2. 引入任务租约、事件 ACK、幂等重试。

交付物：

1. deploy 受控上线流程。
2. 可靠投递闭环。

## 阶段 5：全量评估与收敛（2026-07-13 ~ 2026-07-26）

1. 灰度 50% -> 100% 分批推进。
2. 性能调优、成本评估、文档收敛。

交付物：

1. 上线评审包（指标、风险、回滚）。
2. V1 正式版运行手册。

---

## 8. 灰度与回滚策略

## 8.1 灰度策略

1. 按意图灰度：`LANGGRAPH_INTENTS=analyze,test,...`
2. 按流量灰度：`5% -> 20% -> 50% -> 100%`
3. 按租户灰度：白名单项目先行。

## 8.2 回滚策略

1. 一键切换 `AGENT_ENGINE=legacy`。
2. 保留老链路代码直到新链路稳定 2 个迭代周期。
3. 任一红线触发立即回滚。

红线建议：

1. 成功率下降超过 1%。
2. P95 上升超过 20%。
3. 重复执行率超过 0.1%。
4. 事件丢失率超过 0.01%。

---

## 9. 验收指标（上线门槛）

1. 任务成功率：不低于基线且提升 >= 2%。
2. 性能：P95 下降 >= 20%（重点链路 `code_change`）。
3. 稳定性：结构化解析错误率下降 >= 70%。
4. 可靠性：重复执行率 < 0.1%，事件丢失率 < 0.01%。
5. 运维性：关键链路 trace 覆盖率 >= 95%。

---

## 10. 风险与应对

1. 风险：依赖升级导致 API 变化。  
应对：版本锁定、周级升级窗口、自动化回归。
2. 风险：编排迁移期间语义偏差。  
应对：双写对比（legacy 与 langgraph 输出比对）。
3. 风险：性能回退。  
应对：缓存、并行化、节点级超时预算。
4. 风险：团队学习成本。  
应对：统一模板、示例图、代码走查清单。

---

## 11. 立即执行清单（两周内）

1. 建立双引擎开关与配置项。
2. 为 Intent/Planner 定义统一 schema。
3. 建立最小 LangGraph PoC（analyze/test）。
4. 增加核心指标埋点与 dashboard 草版。
5. 输出第一版灰度发布与回滚 SOP。

---

## 12. 最终建议

1. 这次升级值得做，且应该现在做。
2. 路线必须是渐进式，而不是重写式。
3. 核心不是“换框架”，而是“提升生产可靠性与可运维性”。
4. LangChain/LangGraph 是加速器，不应替代你们已有的优秀控制面与事件模型。

