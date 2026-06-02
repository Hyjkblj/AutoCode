# AutoCode 多 Agent 架构评分报告

> 评估日期: 2026-05-13

---

## 总览

| 层 | 模块 | 评分 | 一句话评价 |
|----|------|------|-----------|
| Python Agent | 编排能力 | **78** | DAG 并行+双引擎+fix loop，但 DAG 功能有限、无声明式工作流 |
| Python Agent | Agent 设计 | **75** | 职责清晰+统一事件发布，但接口不统一、可扩展性不足 |
| Python Agent | 事件协议 | **85** | 18 种事件+成熟 ACK+去重+版本化+语义文档齐全 |
| Python Agent | 工具链 | **70** | 安全约束+验证门+智能修复，但种类少、无注册机制 |
| Python Agent | 插件系统 | **80** | Protocol 接口+Manifest 驱动+三维安全策略+熔断器隔离 |
| Python Agent | 可观测性 | **82** | 三层体系（追踪+指标+日志）+缓存监控+自动修复 |
| Python Agent | 容错机制 | **80** | 熔断器+分布式锁+Outbox+重启恢复+fix loop 迭代限制 |
| Python Agent | LLM 集成 | **76** | 多后端+Profile+LRU+TTL 缓存+语义缓存+监控 |
| Java 控制面 | 任务状态机 | **85** | 转换规则完整+终态保护到位，PAUSED 未实现、硬编码 |
| Java 控制面 | 事件存储 | **88** | seq 分配健壮+去重/幂等完善，缺快照机制和 payload 索引 |
| Java 控制面 | 审批机制 | **82** | 审批上下文绑定是亮点，缺超时和多人会签 |
| Java 控制面 | 队列设计 | **80** | 三后端+DB 调度+租约回收合理，RabbitMQ 实现粗糙 |
| Java 控制面 | WebSocket | **78** | 事务感知广播设计好，SimpleBroker 不支持集群 |
| Java 控制面 | 安全机制 | **75** | JWT+mTLS+项目级授权+审计哈希链层次分明，默认值偏开发 |
| Android App | UI 架构 | **55** | 单文件 2340 行，无 Preview/深色模式，Compose 用法规范 |
| Android App | 状态管理 | **50** | 单向数据流+StateFlow 正确，God ViewModel 2293 行 |
| Android App | 事件消费 | **70** | STOMP WebSocket 完整，断线重连+seq 补拉+Room 缓存 |
| Android App | 导航设计 | **60** | 双层 NavHost+底部导航合理，路由硬编码、无 Deep Link |
| Android App | 数据层 | **55** | REST API 覆盖全面，无 Repository 抽象、手动 JSON 解析 |

---

## 综合评分

| 层 | 加权分 |
|----|--------|
| Python Agent | **78/100** |
| Java 控制面 | **81/100** |
| Android App | **57/100** |
| **整体** | **73/100** |

---

## 各维度详细分析

### 一、Python Agent (78/100)

#### 1. 编排能力 (78)

**优势:**
- DAG 调度器基于 ThreadPoolExecutor，支持依赖声明、循环检测、FIRST_EXCEPTION 快速失败
- 双引擎架构 (legacy + langgraph)，LangGraph 不可用时自动降级
- Fix Loop 最多 3 次迭代，每次包含 code generation → validation → review+test
- 分布式锁支持 Redis (Lua 脚本) + 本地内存双后端，自动续期

**短板:**
- DAG 仅用于并行 review+test，不支持优先级/超时/重试
- LangGraph 集成偏浅，仅支持 analyze 和 test 两个意图
- 无声明式工作流定义，编排逻辑硬编码在 AgentOrchestrator 中
- 无动态编排能力

#### 2. Agent 设计 (75)

**优势:**
- 5-Agent 职责清晰：IntentAgent → PlannerAgent → CoderAgent → ReviewerAgent → TesterAgent
- BaseAgent 提供统一事件发布 + 序列号管理 + Outbox 模式
- IntentAgent 具备 LLM + 启发式双路径，失败时自动降级
- PlannerAgent/ReviewerAgent 有 fallback 计划

**短板:**
- CoderAgent 和 TesterAgent 不继承 BaseAgent，outbox 机制不统一
- 缺乏 Agent 间通信协议，通过 orchestrator 中间变量传递
- 新增 Agent 类型需修改 orchestrator 代码，缺乏注册机制
- 类型标注不完整，大量 `dict[str, Any]`

#### 3. 事件协议 (85) — 最高分

**优势:**
- 18 种 EventType 覆盖完整任务生命周期
- 7 种 TaskStatus，文档明确标注前置/后置状态
- ACK 协议成熟：accepted/duplicate/errorCode + 8 种错误码
- 双层去重：Redis 快速路径 (24h TTL) + DB 唯一约束
- 语义文档齐全 (docs/semantics/)
- eventVersion 支持协议演进
- shared-protocol 独立 Maven 模块，Java/Python 共享

**短板:**
- payload 是 `Map<String, Object>`，无运行时 schema 校验
- 缺少事件溯源的状态快照和 replay 机制

#### 4. 工具链 (70)

**优势:**
- ExecTool 通过 HTTP 调用 sandbox，支持健康检查/超时/approval
- FileTool 基于白名单防止路径逃逸
- ValidationGate 覆盖 web/backend/fullstack 三种 target
- FixLoop 具备错误分类 + 规则修复 + LLM 辅助修复

**短板:**
- 仅 3 个基础工具 (exec/file/search)，缺少 git/HTTP/DB
- SearchTool 仅支持大小写不敏感文本搜索
- 无工具注册和发现机制

#### 5. 插件系统 (80)

**优势:**
- Protocol 定义三种插件接口 (Reviewer/Generator/Tester)
- Manifest 驱动声明式加载
- 四维权限 (workspace_read/write, sandbox_exec, network_access)
- 三级策略 (全局/环境/项目) + default_deny
- CircuitBreaker 隔离 + 资源限制 (内存/CPU/FD/进程/时间)
- 审批工作流：风险分数计算 (sandbox_exec +0.4, network +0.3, write +0.2)
- 审计追踪全生命周期

**短板:**
- 只支持 reviewer/generator/tester 三种类型
- 资源限制在 Windows 上不可用 (resource.setrlimit)

#### 6. 可观测性 (82)

**优势:**
- 三层体系：分布式追踪 (trace_id/span_id) + Prometheus 指标 (4 类) + 结构化日志
- CacheMonitor 后台线程实时监控缓存性能，critical 告警触发自动修复
- 自动注入 trace 上下文到事件 payload
- Fix Loop 追踪每次修复尝试

**短板:**
- 自研追踪，未集成 OpenTelemetry/Jaeger/Zipkin
- Prometheus 指标缺少 /metrics 端点
- 告警仅支持回调和日志

#### 7. 容错机制 (80)

**优势:**
- CircuitBreaker 三态模型 (closed/open/half_open)，用于 LLM 和插件隔离
- 分布式锁 Redis + 本地内存双后端，Redis 不可用时自动降级
- Outbox 模式：Redis 持久化 + Lua 原子性 + 本地 fallback
- 重启恢复服务：扫描未 ACK 事件，批量重投递
- Fix Loop 最大 3 次迭代，全局错误统计追踪

**短板:**
- 熔断仅覆盖 LLM 和插件，缺 sandbox/API 调用熔断
- 重试策略固定，缺少指数退避配置
- 缺少 Bulkhead (隔舱) 模式

#### 8. LLM 集成 (76)

**优势:**
- 多后端：OpenAI 兼容 + Claude，支持自定义 base_url/chat_url
- Profile 配置系统 (JSON 文件 + 环境变量覆盖)
- LRU + TTL 缓存 + 6 种状态统计
- EnhancedCacheManager：语义缓存键 + 响应质量评估 + bad cache 检测 + cache warming

**短板:**
- 仅 2 种后端，缺 Gemini/Cohere/本地模型 (Ollama/vLLM)
- 无流式输出 (SSE)
- 无 token 计数和成本追踪
- 语义缓存基于关键词正则，非 embedding 向量相似度

---

### 二、Java 控制面 (81/100)

#### 1. 任务状态机 (85)

**优势:**
- 7 种状态转换规则完整，终态保护只允许 HEARTBEAT 通过
- 悲观锁 (findOptionalByIdForUpdate) 保证并发安全
- 信息类事件与状态变更事件区分清晰
- FAILED 指数退避重试：baseBackoff * 2^min(6, retryCount)

**短板:**
- PAUSED 状态定义但从未使用
- default 分支返回 true，未知事件静默通过
- 状态转换硬编码在方法中，非状态机框架

#### 2. 事件存储 (88) — 最高分

**优势:**
- seq 由控制面统一分配，(taskId, seqNum) 唯一约束
- alignNextSeq 防 crash 后 seq 空洞
- 基于 eventId 去重 + 幂等键 (SHA-256 派生 taskId)
- 按 seq 增量拉取，最多 200 条/次
- pushSystemEvent 有唯一约束冲突重试

**短板:**
- payload 以 JSON 字符串存储，无法高效索引
- 无事件快照机制
- schema 演进无版本迁移逻辑

#### 3. 审批机制 (82)

**优势:**
- 审批上下文绑定：action/tool/workspaceRef/inputsHash/command/cwd
- TOOL_START 和 DEPLOY_PLAN 校验实际执行与审批一致性
- 不匹配直接 FAILED + 审计日志

**短板:**
- 单一决策者，不支持多人会签
- 无审批超时，可能永久挂起
- 审批后再次需要审批的场景未处理

#### 4. 队列设计 (80)

**优势:**
- 三后端 (InMemory/Redis/RabbitMQ) + DB 调度模式
- 租约机制：CAS 原子更新 + 5 秒扫描过期任务
- Profile 路由：Agent 声明 profile，只领取匹配任务
- sessionKey 串行化：同 session 任务串行执行

**短板:**
- Redis inflight 无 TTL，ack 丢失会永久残留
- RabbitMQ ack/nack 基本是空实现
- 无优先级、延迟投递

#### 5. WebSocket 推送 (78)

**优势:**
- 事务感知广播：TransactionSynchronizationManager 确保提交后才推送
- 每任务独立 topic
- JWT 认证 CONNECT/SUBSCRIBE/SEND

**短板:**
- SimpleBroker 不支持集群
- 无消息确认机制
- 允许所有来源 (*)
- 无心跳配置

#### 6. 安全机制 (75)

**优势:**
- 双模式认证 (JWT + Token)
- 四角色体系 (AGENT/OPERATOR/ADMIN/VIEWER)
- 项目级授权 (ProjectMembershipEntity)
- mTLS 仅对 Agent 端点强制
- 审计日志 SHA-256 哈希链不可篡改
- 14 个 Flyway 迁移版本

**短板:**
- JWT 默认 secret 硬编码
- CSRF 全局禁用
- CORS 允许所有来源
- /actuator/** 完全公开
- 无速率限制
- JWT 使用 HS256，不适合多服务共享

---

### 三、Android App (57/100)

#### 1. UI 架构 (55)

**优势:**
- Material 3 + Compose BOM 2024.10.01
- AgentEventItem 根据 10+ 种事件差异化渲染
- ApprovalBottomSheet 带倒计时审批弹窗
- multiplatform-markdown-renderer 渲染 diff

**短板:**
- AppUi.kt 单文件 2340 行
- 无 Preview、无深色模式、主题仅 4 个颜色
- 辅助函数与 UI 混杂

#### 2. 状态管理 (50) — 最低分

**优势:**
- MutableStateFlow + collectAsStateWithLifecycle 标准单向数据流
- DataStore 持久化 + Room 事件缓存
- 事件去重 (eventId > seq > content hash 三级策略)

**短板:**
- AppViewModel 单文件 2293 行 (God ViewModel)
- ViewModel 中定义 Room Entity/DAO/Database
- 无 DI 框架 (Hilt/Koin)
- 离线模拟逻辑与远程业务耦合

#### 3. 事件消费 (70)

**优势:**
- STOMP 1.2 完整实现 (帧解析/CONNECT/SUBSCRIBE/心跳)
- 断线重连指数退避 (上限 30s)
- seq 序列号追踪 + 断线补拉
- 认证错误识别 (14 种关键词)
- Room 缓存 + 两级淘汰

**短板:**
- 仅支持单任务订阅
- 轮询固定 3.5s，无自适应退避
- WebSocket scope 未跟随 ViewModel 生命周期

#### 4. 导航设计 (60)

**优势:**
- 双层 NavHost (login/shell + 5 Tab + 子页面)
- 底部导航栏 + popUpTo + saveState + restoreState
- Tab 用 sealed class 类型安全
- 认证状态自动跳转

**短板:**
- 路由字符串硬编码
- 无 Deep Link
- 无页面切换动画

#### 5. 数据层 (55)

**优势:**
- REST API 覆盖全部端点
- 响应解析健壮 (多结构兼容)
- DataStore + Room 离线支持

**短板:**
- 无 Repository 层，ControlPlaneClient 是 object 单例
- 同步 OkHttp + Dispatchers.IO
- 手动 JSON 解析
- 无缓存策略、无请求取消

---

## 雷达图 (各层得分)

```
              事件协议(85)
                 ▲
                 │
    可观测性(82) ┼─────────── 容错机制(80)
                 │
    插件系统(80) ┼─────────── 编排能力(78)
                 │
    LLM集成(76) ┼─────────── Agent设计(75)
                 │
    工具链(70) ──┘

Python Agent: 78

    事件存储(88)
         ▲
         │
状态机(85)┼─── 审批(82)
         │
队列(80) ┼─── WebSocket(78)
         │
安全(75) ┘

Java 控制面: 81

    事件消费(70)
         ▲
         │
导航(60) ┼─── UI(55)
         │
数据层(55)┼─── 状态管理(50)

Android App: 57
```

---

## 与赛题 2 的差距评估

| 能力 | 当前状态 | 差距 |
|------|----------|------|
| Git 操作 | 无 | 需新建 GitTool |
| 代码索引 | 无 | 需新建 CodeIndex |
| 多轮对话 | 无 | 需新建 DialogueManager |
| 增量代码修改 | CoderAgent 仅支持从零生成 | 需重构为增量编辑 |
| 测试生成 | TesterAgent 仅执行已有测试 | 需新建 TestGenerator |
| 全阶段人工介入 | 仅代码执行阶段有审批 | 需新建 HumanGate |
| 知识回写 | RedisMemory 仅存任务记录 | 需扩展知识存储 |

---

## 改进优先级建议

### P0 — 阻塞赛题

1. **新建 GitTool + CodeIndex + RepoBootstrap** — 基础能力
2. **重构 CoderAgent 支持增量修改** — 核心能力
3. **新增 9 个事件类型 + Payload** — 协议扩展

### P1 — 影响质量

4. **拆分 Android AppUi.kt 和 AppViewModel.kt** — 最大技术债
5. **引入 Repository 层 + kotlinx.serialization** — 数据层规范化
6. **补充工具种类 + 工具注册机制** — 可扩展性

### P2 — 生产就绪

7. **集成 OpenTelemetry** — 可观测性标准化
8. **安全默认值收紧** (CORS/actuator/JWT secret) — 安全加固
9. **WebSocket 集群支持** (Redis broker) — 水平扩展
10. **LLM 流式输出 + token 统计** — 成本控制
