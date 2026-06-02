
# PR Roadmap — 系统完善补充任务

基于 `系统完善整体方案-2026-05.md` 完成度评估（~58%），本文件定义后续最小 PR 清单。
每个 PR 聚焦单一目标，可独立合入。

**当前分支：** `feature/system-improvement-2026-05`
**基准：** master（已含 PR-1 至 PR-7 + PR-3b、PR-4b）

---

## PR-8：契约测试扩面（阶段 A 补齐）

**目标：** 将契约测试从仅覆盖 event_ack 扩展到核心事件和沙箱协议
**工作流：** 2 — 契约与兼容性治理
**里程碑：** M2

改动范围：


| 文件 | 动作 |
|---|---|
| `shared-protocol/.../SchemaContractTest.java` | 新增 task_event、sandbox_health、sandbox_execute 的契约测试方法 |
| `python-agent/tests/test_schema_contract.py` | 新增 Python 侧对 task_event、sandbox 协议的 schema 校验测试 |

验收标准：
- `mvn -pl shared-protocol test` 通过
- `pytest python-agent/tests/test_schema_contract.py` 通过
- 覆盖 event_ack + task_event + sandbox_health + sandbox_execute 四种协议

---

## PR-9：AI Pipeline 告警规则（阶段 C 启动）

**目标：** 补齐生成链路告警，让 Grafana 面板可告警
**工作流：** 5 — 生产可运维化
**里程碑：** M4

改动范围：

| 文件 | 动作 |
|---|---|
| `ops/observability/alert_rules.yml` | 新增 `PipelineStageHighFailureRate`、`PipelineStageSlowP95`、`AgentDown` 告警规则 |
| `ops/observability/alertmanager.yml` | 确认 pipeline 告警路由到正确 receiver |

验收标准：
- `promtool check rules ops/observability/alert_rules.yml` 通过
- 告警规则覆盖：stage 失败率 >10%、P95 延迟 >30s、agent 不可达 >2m

---

## PR-10：事件处理逻辑边界显式化（阶段 B 启动）

**目标：** 将控制面中事件接收/去重/ACK 生成的代码从 TaskService 中解耦到独立 package
**工作流：** 4 — 服务边界重构
**里程碑：** M3

改动范围：

| 文件 | 动作 |
|---|---|
| `control-plane-spring/.../service/protocol/EventIngressService.java` | 新建，从 TaskService 提取事件接收+去重+ACK 逻辑 |
| `control-plane-spring/.../service/TaskService.java` | 移除已提取的事件处理逻辑，委托给 EventIngressService |
| `control-plane-spring/.../api/AgentController.java` | 注入 EventIngressService 替代直接调用 TaskService |

验收标准：
- `mvn -pl control-plane-spring compile` 通过
- 现有测试不回归
- TaskService 行数减少，EventIngressService 职责一句话可说清

---

## PR-11：ValidationGate fullstack 支持（阶段 A 补齐）

**目标：** 让 ValidationGate 同时支持 fullstack target 的校验规则
**工作流：** 3 — 执行与生成体系收敛
**里程碑：** M1

改动范围：

| 文件 | 动作 |
|---|---|
| `python-agent/generators/validation_gate.py` | 新增 `target == "fullstack"` 分支，校验 backend + frontend 必需文件 |
| `python-agent/tests/test_validation_gate.py` | 新增 fullstack 校验的单元测试 |

验收标准：
- `pytest python-agent/tests/test_validation_gate.py` 通过
- fullstack target 校验覆盖：backend/app.py、frontend/package.json、docker-compose.yml、README.generated.md

---

## PR-12：状态机迁移表与非法事件审计（阶段 A 补齐）

**目标：** 用代码定义合法状态迁移，非法事件被拒绝并记录审计日志
**工作流：** 1 — 主链路稳定化
**里程碑：** M1

改动范围：

| 文件 | 动作 |
|---|---|
| `control-plane-spring/.../service/TaskStateMachine.java` | 新建，定义合法状态迁移 Map + validate(event, currentStatus) 方法 |
| `control-plane-spring/.../service/TaskService.java` | 调用 TaskStateMachine 校验迁移合法性 |
| `control-plane-spring/.../service/audit/AuditService.java` | 新增 `logIllegalTransition(taskId, event, currentStatus)` |

验收标准：
- `mvn -pl control-plane-spring compile` 通过
- 合法迁移表覆盖：CREATED→RUNNING→SUCCEEDED/FAILED/CANCELLED
- 非法迁移写入审计日志且不改变任务状态

---

## PR-13：Python 侧日志结构化（阶段 C 推进）

**目标：** 统一 Python agent 日志字段，与控制面对齐
**工作流：** 5 — 生产可运维化
**里程碑：** M4

改动范围：

| 文件 | 动作 |
|---|---|
| `python-agent/utils/observability.py` | `log_structured()` 默认携带 taskId、stage、traceId 字段 |
| `python-agent/agents/base_agent.py` | 关键路径日志统一使用 `log_structured()` |
| `python-agent/client/control_plane_client.py` | 请求/响应日志携带 taskId 和 status |

验收标准：
- 所有 INFO 级别日志包含 `taskId` 和 `stage` 字段（至少在 task 执行路径上）
- `log_structured()` 被 base_agent 和 control_plane_client 调用

---

## PR-14：ADR 模板与首个补充 ADR（阶段 D 基础）

**目标：** 建立 ADR 流程模板，为后续架构决策提供标准化记录
**工作流：** 6 — 工程化与治理体系
**里程碑：** 持续

改动范围：

| 文件 | 动作 |
|---|---|
| `docs/adr/000-adr-template.md` | 新建 ADR 模板（背景、决策、后果三段式） |
| `docs/adr/003-event-boundary-extraction.md` | 记录 PR-10 事件边界提取的架构决策 |

验收标准：
- ADR 模板存在且格式清晰
- PR-10 的决策有对应 ADR 记录

---

## 执行顺序

```
PR-8  (契约测试)     ──┐
PR-9  (告警规则)      │  可并行
PR-11 (ValidationGate) ──┘
                         │
PR-12 (状态机)       ────┤  依赖 PR-8 验证
PR-10 (事件边界)     ────┤  依赖 PR-12
                         │
PR-13 (日志结构化)   ────┤  独立
PR-14 (ADR 模板)    ────┘  独立
```

建议先做 PR-8、PR-9、PR-11（可并行），再做 PR-12 和 PR-10。

---

## 完成后预期评估变化

| 维度 | 当前 | PR 全部完成后 |
|---|---:|---:|
| 协议与契约治理 | 7.6 | ~8.2 |
| 服务边界清晰度 | 7.2 | ~7.6 |
| 可观测性与运维可见性 | 8.3 | ~8.5 |
| 可靠性与韧性 | 7.7 | ~8.0 |
| 可维护性 | 7.0 | ~7.4 |
| 综合分 | 7.7 | ~8.0 |
