# AutoCode 后端升级优先级总表

更新时间：2026-05-01  
适用范围：`control-plane-spring`、`pc-agent-java`、`python-agent`、`shared-protocol`  
汇总依据：

1. `docs/升级2.0/backend-upgrade-master-plan-2026-04.md`
2. `docs/升级2.0/backend-generation-solution-2026-04.md`
3. `docs/升级2.0/langchain-langgraph-agent-upgrade-plan-2026-04.md`
4. `docs/升级2.0/adr-002-p2-platformization-gateway-observability.md`
5. `docs/升级2.0/p2-platform-runbook.md`
6. `docs/升级2.0/p2-troubleshooting-guide.md`
7. `docs/升级2.0/p2-performance-tuning-guide.md`
8. `docs/升级2.0/架构评分.md`
9. `docs/升级2.0/智能体设计评分.md`

---

## 1. 汇总结论

当前仓库的后端升级不再是“从零开始”，而是“V1 已在线稳定交付，V2 后端底座也已基本成型，但还没有完全进入稳定生产态”。

基于 2026-05-01 的代码、文档与当前补充事实，建议采用下面的总策略：

1. 先确认本地/联调基线可随时拉起，不把临时停 Docker 误判为系统不可运行。
2. 先补齐可靠性最后一公里。
3. 再把后端生成链路做实做稳。
4. 同时把测试覆盖和回归门禁拉起来。
5. 将框架升级纳入正式计划，而不是停留在讨论层。
6. Gateway 目标态采用 `Spring Cloud Gateway`，Python 侧采用 `LangChain + LangGraph` 渐进升级，Java 侧采用渐进式 Spring Cloud 微服务拆分。

一句话版本：

**先把联调基线、可靠性、测试和生成闭环做稳，再按蓝图推进 Spring Cloud Gateway、LangGraph 与 Java 微服务化。**

---

## 2. 当前后端服务状态

### 2.0 现网基线说明

需要先区分“线上已验证能力”和“当前本机后端运行态”：

1. 项目 V1 已经在服务器上稳定部署。
2. V1 已经具备“生成纯前端 Web”的稳定交付能力。
3. 本文关注的是 `升级2.0` 语境下的后端能力补齐与本机运行基线，而不是否定 V1 已有线上成果。
4. 因此当前更准确的判断应是：**产品 V1 已在线可用，但 V2 后端链路在本地与工程化层面仍需补齐。**

### 2.1 本机运行态

截至 2026-04-30 检查时，本机状态如下：

| 项 | 当前状态 | 结论 |
|---|---|---|
| Docker Desktop Daemon | 检查时未连接 | 当次检查时 Docker 处于暂停状态，不代表本机无法拉起全栈 |
| MySQL `3306` | 监听中 | 本机有数据库基础能力 |
| Control Plane `8058` | 未监听 | 控制面当前未运行 |
| Java Sandbox `18080` | 未监听 | Java Agent 当前未运行 |
| Gateway `8080` | 未监听 | 网关当前未运行 |
| Prometheus `9090` / Grafana `3000` / Alertmanager `9093` | 未监听 | 平台化观测栈当前未运行 |

结论：

1. 线上 V1 是稳定可用的，本机 V2 也具备拉起条件，只是 2026-04-30 检查时 Docker 暂停，未处于运行态。
2. 所以后续升级排序里，`联调基线确认` 的含义应理解为“确保本地/联调/验收环境可快速拉起”，而不是“从零恢复线上产品能力”。
3. 对 2.0 升级来说，它是所有改造动作的前置条件，但不再单独代表最高战略风险。

### 2.2 代码落地状态

| 能力域 | 当前判断 | 说明 |
|---|---|---|
| Control Plane 任务底座 | 已较完整 | 已有任务幂等、租约回收、事件去重、顺序号、审批、制品、RBAC、审计链 |
| Java 执行安全 | 已较完整 | 已有命令白名单、提权检测、环境变量检测、网络限制、路径限制、审批绑定 |
| Python 编排主干 | 已较完整 | 已有 Intent/Planner/Coder/Reviewer/Tester/Orchestrator + DAG |
| Python 可靠性增强 | 部分完成 | 已有重试发布、内存 outbox、分布式锁、熔断器，但还不是完整持久化闭环 |
| 后端生成能力 | 已最小可用 | 已有 `backend/fullstack` 生成器和 `validation_gate`，但仍是模板化最小实现 |
| LangGraph 迁移 | 部分完成 | 已有双引擎路由，当前只覆盖 `analyze/test`，仍需继续接管主链路 |
| 平台化与观测 | 部分完成 | 已有 `gateway + prometheus + grafana + alertmanager` 配置；当前仓库骨架偏 `nginx`，2.0 目标态需收敛为 `Spring Cloud Gateway` |
| 工程质量 | 仍偏弱 | CI 已落地，但测试覆盖率和集成验证仍不足 |

---

## 3. 规划落地状态校正

为避免重复投入，先把原规划拆成三类。

### 3.1 已基本落地，可直接复用

1. 控制面任务幂等、事件去重、队列 ack/nack、租约回收。
2. Java Agent 策略链、安全门禁、审批上下文绑定。
3. Python 双引擎开关 `legacy | langgraph`。
4. Python `CircuitBreaker`、`DistributedTaskLock`、`RedisMemory`、LLM Cache。
5. Python 插件系统与最小平台化文档。
6. GitHub Actions 最小 CI 已存在。

### 3.2 已部分落地，但还不能算完成

1. Python 事件可靠投递。
   当前已有重试和内存 outbox，但缺少持久化 outbox、明确 ACK 契约、重启后的 seq 连续性治理。
2. 后端生成链路。
   当前已有 Flask + SQLite 模板生成、fullstack 组合生成和基础校验，但仍偏模板化，缺少更强的运行验证与修复闭环。
3. LangGraph 迁移。
   当前只有 `analyze/test` 进入 LangGraph，`code_change/deploy` 还没迁移。
4. 平台化观测栈。
   当前 compose 和配置已在仓库，但未形成稳定运行基线与值班闭环；Gateway 方案也需要从过渡骨架收敛到 `Spring Cloud Gateway`。
5. 框架升级路线。
   方向已经明确为“Java 渐进式 Spring Cloud 化 + Python LangChain/LangGraph 渐进升级”，但还没有冻结服务边界、迁移顺序和回退策略。

### 3.3 仍是明确缺口

1. 全栈运行基线恢复与冒烟验收。
2. 测试覆盖率达到阶段目标并形成硬门禁。
3. 事件可靠性真正达到“进程异常后仍可恢复”的级别。
4. 后端生成结果可运行率和 fix-loop 成熟度。
5. 统一超时预算、异常分层、结构化日志标准。
6. LangGraph 核心链路迁移与灰度对比。
7. 性能压测、容量基线和连接池调优。
8. Java Spring Cloud 微服务边界、Spring Cloud Gateway 路由和 Python 框架升级蓝图定版。

---

## 4. 总优先级排序

## P0-0 联调基线确认与快速冒烟

### 目标

先确保当前后端最小闭环可以被快速拉起，形成后续升级的真实验收面。

### 为什么排第一

1. 2026-04-30 的检查时刻 `8058/18080/8080/9090/3000/9093` 都未监听，但这是临时停 Docker 的观测结果。
2. 后续所有可靠性、性能、灰度计划都仍然需要稳定联调面来验证。
3. 由于 V1 已在线稳定，2.0 本地基线确认的目标是为后端升级验收提供环境，而不是替换现网 V1。

### 关键动作

1. 固化本机 Docker 启停说明，明确最小依赖与启动顺序。
2. 按 `docker compose --profile fullstack --profile platform up -d` 拉起最小平台环境。
3. 验证以下健康点：
   `8058 /actuator/health`
   `18080 /sandbox/health`
   `8080 /healthz`
   `9090`
   `3000`
4. 运行 `scripts/smoke-test.ps1` 或补一套后端最小冒烟脚本。

### 涉及模块

1. `docker-compose.yml`
2. `ops/gateway/*`
3. `ops/observability/*`
4. `scripts/*`

### 验收标准

1. Control Plane、Java Agent、Python Agent、Gateway、Prometheus、Grafana 均可访问。
2. 至少完成一次“建任务 -> 拉任务 -> 执行 -> 事件上报 -> 制品可见”的端到端冒烟。
3. 不影响现网 V1 纯前端生成能力的正常交付节奏。

---

## P0-1 补齐事件可靠性最后一公里

### 目标

把当前“部分可靠”升级为“可恢复、可重放、可确认”的端到端闭环。

### 当前判断

已完成一半以上，但还不够稳。

1. Control Plane 已支持事件去重、seq、租约、ack/nack。
2. Python `BaseAgent` 已有重试发布和内存 outbox。
3. 但 outbox 仍是进程内存级，重启后不保留。
4. 事件 ACK 仍偏“接口成功即视为接收”，缺少更明确的已接收语义。

### 关键动作

1. 为 Python 事件发布增加 Redis 持久化 outbox。
2. 增加 ACK 语义字段，例如 `ack/acceptedSeq/duplicate/errorCode`。
3. 明确 Python seq 与 Control Plane seq 的关系，避免重启后语义不清。
4. 为事件投递失败、重复、恢复增加 metrics 和结构化日志。

### 涉及模块

1. `python-agent/agents/base_agent.py`
2. `python-agent/client/control_plane_client.py`
3. `python-agent/memory/redis_memory.py` 或独立 outbox 存储
4. `control-plane-spring` 事件接收与响应 DTO
5. `shared-protocol` 事件/ACK 契约

### 验收标准

1. 控制面短时不可用后恢复，事件最终可达。
2. Python Agent 进程重启后，未确认事件不会静默丢失。
3. 重复事件不会造成重复业务副作用。

---

## P0-2 做实后端生成闭环

### 目标

把“最小模板可用”提升到“稳定生成可运行后端”。

### 当前判断

这一块已经有明显进展，但还不能算成熟交付链路。

1. 已支持 `backend`、`fullstack` 生成。
2. 已有 `validation_gate` 和 artifact 打包。
3. 当前仍以 Flask + SQLite 模板为主，能力边界比较窄。
4. 运行验证仍偏静态校验，真实启动和接口冒烟不足。

### 关键动作

1. 扩展生成结果的结构化约束。
2. 增加启动级验证、接口级验证、依赖完整性验证。
3. 完善 fix-loop 的失败分类和回修策略。
4. 补全 `requirements`、运行说明、runtime descriptor 与 artifact 元数据。
5. 明确后端生成第一阶段只收敛 `Flask + SQLite CRUD`，避免过早扩栈。

### 涉及模块

1. `python-agent/agents/coder_agent.py`
2. `python-agent/generators/backend_generator.py`
3. `python-agent/generators/fullstack_generator.py`
4. `python-agent/generators/validation_gate.py`
5. `python-agent/orchestrator/agent_orchestrator.py`

### 验收标准

1. 后端生成任务可运行率达到阶段目标。
2. 对 `todo/blog/user` 等典型需求，产物能启动并返回基础 API。
3. 失败任务能明确区分“生成失败 / 校验失败 / 启动失败 / 测试失败”。

---

## P0-3 把测试和门禁补到可重构水平

### 目标

为后续 LangGraph 迁移、可靠性改造和平台化放量建立回归保护。

### 为什么当前优先级很高

1. CI 已有，但测试覆盖率仍不是当前代码复杂度可接受的水平。
2. 当前最危险的不是“没功能”，而是“功能已多，但改动没有足够回归保护”。

### 关键动作

1. Java 侧补 TaskService、审批状态机、事件摄取、Artifacts、Security 策略测试。
2. Python 侧补 Orchestrator、BaseAgent reliable publish、DistributedTaskLock、Fix Loop、Backend Generator 测试。
3. 增加最小 E2E：任务创建、事件流、artifact 上传、hosted site。
4. 引入覆盖率报告与阈值门禁。

### 涉及模块

1. `control-plane-spring/src/test/*`
2. `pc-agent-java/src/test/*`
3. `python-agent/tests/*`
4. `.github/workflows/ci.yml`
5. 根 `pom.xml` 与 Python coverage 配置

### 验收标准

1. Java/Python 核心后端覆盖率向 `>=70%` 阶段目标推进。
2. PR 合入前必须经过 `mvn test + pytest + compile check`。
3. 关键链路改动可通过自动化回归挡住回退风险。

---

## P0-4 统一超时预算、异常模型和结构化日志

### 目标

让失败更快暴露、可直接定位、可按节点回退。

### 当前判断

1. `CircuitBreaker` 已落地。
2. 但超时预算还不是统一模型。
3. Python 侧仍有较多宽泛异常处理。
4. 日志、错误码、阶段诊断还不够统一。

### 关键动作

1. 统一异常类型：`LLMError`、`SandboxError`、`ValidationError`、`ProtocolError`、`PluginError`。
2. 为 Intent/Planner/Coder/Reviewer/Tester/ExecTool 增加阶段级 timeout。
3. 统一结构化日志字段：
   `taskId`
   `traceId`
   `runId`
   `intent`
   `planName`
   `errorCode`
   `eventType`
4. 对 fix-loop、breaker、plugin fallback 单独打点。

### 涉及模块

1. `python-agent/llm/llm_client.py`
2. `python-agent/orchestrator/agent_orchestrator.py`
3. `python-agent/agents/*`
4. `python-agent/utils/errors.py`
5. `python-agent/utils/observability.py`

### 验收标准

1. 任一失败任务都能快速定位到具体节点与错误类别。
2. 长尾阻塞任务有超时退出而不是无限挂起。
3. 日志和终态 payload 可直接用于排障。

---

## P1-0 冻结框架升级蓝图

### 目标

把“想做框架升级”收敛为“可执行、可灰度、可回退”的正式升级蓝图。

### 当前判断

框架升级方向已经明确，但缺少统一落地顺序。

1. Java 侧目标是从当前 Spring Boot 控制面逐步走向 Spring Cloud 微服务化。
2. Python 侧目标是 `LangChain` 作为能力层、`LangGraph` 作为编排内核的渐进升级。
3. Gateway 目标态应采用 `Spring Cloud Gateway`，现有 `nginx` 仅保留为过渡骨架或本地兼容方案。
4. 当前仍缺少服务边界、注册配置、灰度切换与回退策略的统一蓝图。

### 关键动作

1. 明确 Java 服务拆分边界：任务控制面、事件接入、制品服务、审批/审计、站点发布等职责归属。
2. 明确 Python 编排升级边界：哪些意图继续走 `legacy`，哪些先迁到 `LangGraph`，哪些能力统一通过 `LangChain` 适配。
3. 明确 Gateway 路由、鉴权透传、超时预算、限流和追踪头方案，并以 `Spring Cloud Gateway` 为目标态。
4. 设计统一灰度与回退策略：按意图、按租户、按环境、按路由逐步切换。
5. 输出迁移蓝图、版本边界、里程碑和风险清单。

### 涉及模块

1. `control-plane-spring/*`
2. `shared-protocol/*`
3. `python-agent/orchestrator/*`
4. `python-agent/llm/*`
5. `ops/gateway/*` 与未来独立 Gateway 服务模块

### 验收标准

1. 有一份明确的 Java 微服务边界图与拆分顺序。
2. 有一份 Python `LangChain + LangGraph` 迁移矩阵与灰度策略。
3. 有一份 `Spring Cloud Gateway` 路由/过滤器/回退方案说明。
4. 三条升级主线都具备“可分批上线、可快速回退”的执行条件。

---

## P1-1 迁移 LangGraph 核心链路

### 目标

在保持 `legacy` 可回退前提下，把 Python 主链路渐进迁移到 `LangGraph`，并通过 `LangChain` 统一模型/工具能力层。

### 当前判断

当前只有 `analyze/test` 进入 LangGraph，主链路尚未迁移，`LangChain` 能力层也还没有完全统一到迁移蓝图下。

### 关键动作

1. 先迁 `code_change`。
2. 再迁 `backend/fullstack generation`。
3. 最后迁 `deploy + approval`。
4. 将结构化输出、Tool Adapter、模型调用统一收口到 `LangChain` 能力层。
5. 保持按意图灰度和双写比对。

### 验收标准

1. `code_change` 结果与 legacy 对比一致率达标。
2. 灰度期成功率、P95、重复执行率不劣于基线。

---

## P1-2 落地 Spring Cloud Gateway 与全链路可观测性

### 目标

把当前已有的 Gateway 骨架、metrics、terminal observability、Prometheus/Grafana 基线，升级为 `Spring Cloud Gateway + 统一观测` 的可值班体系。

### 当前判断

1. 当前仓库已有 Gateway 骨架，但主要偏 `nginx` 过渡方案。
2. 2.0 目标态需要统一到 `Spring Cloud Gateway`，这样更便于和 Java 侧 Spring Cloud 化、鉴权透传、灰度路由、限流熔断保持同一技术面。
3. 可观测性建设需要和 Gateway 迁移一起推进，避免入口层再次成为盲区。

### 关键动作

1. 新增独立 Gateway 服务模块，采用 `Spring Cloud Gateway` 承担统一入口。
2. 为 Gateway 增加路由、Rewrite、认证透传、TraceId 透传、超时、限流和降级过滤器。
3. Control Plane 增加业务级 metrics：
   任务创建
   任务分发
   事件摄取
   租约恢复
   artifact 上传
4. Python Agent 对关键 span、cache、breaker、fix-loop、plugin fallback 做统一指标输出。
5. Gateway 层补超时、上游异常、代理耗时、路由命中、限流触发等指标。

### 验收标准

1. `http://localhost:8080` 由 `Spring Cloud Gateway` 提供统一入口。
2. 关键主链路 trace 覆盖率达到目标。
3. 故障时能从 Dashboard 快速定位到 Gateway、控制面、LLM、Sandbox 或插件侧问题。

---

## P1-3 做性能验证而不是只做性能猜测

### 目标

建立容量与时延基线，再决定是否继续异步化和扩栈。

### 关键动作

1. 明确 P95、吞吐、失败率、重试率基线。
2. 做数据库连接池、Redis、WebSocket 广播、LLM 调用热点分析。
3. 引入固定压测脚本与阶段性报告。

### 验收标准

1. P95 与吞吐提升有数据佐证。
2. 灰度过程中性能回退能快速触发回滚。

---

## P2-1 Java 渐进式 Spring Cloud 微服务化

### 目标

在不破坏 V1 线上稳定性的前提下，把当前 Java 控制面从“模块化单体”逐步升级为可灰度、可回退的 Spring Cloud 微服务体系。

### 关键动作

1. 先做包级/模块级边界收敛，再做进程级拆分，避免一次性把领域问题转成分布式问题。
2. 优先抽离边界最清晰、对外接口最稳定的服务，例如站点发布、制品访问、网关后置能力。
3. 按业务价值与耦合度评估任务控制面、事件接入、审批审计的拆分时机。
4. 配套完善服务注册发现、配置管理、健康检查、灰度发布和回退机制。
5. 与 `Spring Cloud Gateway`、Prometheus/Grafana、运行文档一起形成完整平台运行面。

### 验收标准

1. 至少有一条 Java 子能力链路完成独立服务化并稳定接入主流程。
2. 微服务拆分后，任务主链路成功率、P95、错误率不劣于拆分前基线。
3. 健康检查、5xx、JVM/Redis、路由级告警可实际触发与回收。

---

## P2-2 继续做成本治理与生态扩展

### 目标

在稳定性达标后，再扩大缓存、插件和多技术栈生态。

### 关键动作

1. 细化 LLM Cache 命中率与坏缓存治理。
2. 扩展插件白名单、隔离策略和能力审批。
3. 扩后端生成技术栈，但必须在单栈收敛后再做。

---

## 5. 建议执行顺序

建议按下面顺序推进，而不是按所有文档原顺序平均铺开：

1. `P0-0` 联调基线确认与快速冒烟
2. `P0-1` 事件可靠性最后一公里
3. `P0-3` 测试与 CI 门禁强化
4. `P0-2` 后端生成闭环做实
5. `P0-4` 超时、异常、日志标准化
6. `P1-0` 冻结框架升级蓝图
7. `P1-1` LangGraph 核心链路迁移
8. `P1-2` Spring Cloud Gateway 与可观测性
9. `P1-3` 性能验证与调优
10. `P2-1` Java Spring Cloud 微服务化
11. `P2-2` 成本治理与生态扩展

原因很简单：

1. 当前最缺的是“可验证、可回归、可灰度”。
2. 框架升级应该进入正式计划，但必须建立在可靠性与回归保护之上。
3. `Spring Cloud Gateway`、LangGraph 和 Java 微服务化都应按蓝图渐进落地，而不是并行大重构。

---

## 6. 本轮建议产出物

建议本轮升级汇总之后，按顺序继续补以下交付物：

1. 后端最小启动与冒烟清单。
2. 事件 ACK 与 outbox 升级设计。
3. 后端生成能力验收清单。
4. 覆盖率与 E2E 测试计划。
5. Java Spring Cloud 服务拆分边界图。
6. `Spring Cloud Gateway` 路由与过滤器设计。
7. LangGraph 核心链路迁移拆解表。
8. V1 纯前端生成能力的兼容性与灰度切换约束清单。

---

## 7. 最终建议

当前 AutoCode 更准确的状态不是“产品还没跑起来”，而是“V1 已经稳定在线，V2 后端能力建设快于工程收敛速度，而框架升级方向也已经需要进入正式落地阶段”。

所以本轮总升级不建议再分散注意力去做一次性大重构。更合适的策略是“保住 V1 线上能力，先做可靠性与回归闭环，再按蓝图推进 Spring Cloud Gateway、Python 编排升级和 Java 微服务化”。最合理的排序是：

1. 先确认服务运行面随时可拉起。
2. 再补可靠性持久化闭环。
3. 同步补测试门禁和生成质量门禁。
4. 先冻结框架升级蓝图。
5. 最后分批做 LangGraph 主链路迁移、Spring Cloud Gateway 接管和 Java 微服务化。

这份总表的核心判断是：

**当前后端已经具备升级的底座，但还没有具备大规模放量的收敛度。**
