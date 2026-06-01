# 前端升级改造分析文档

> 生成日期: 2026-05-27
> 基准: `docs/stitch/current-ui-design/` (14 屏 Stitch 导出) vs Android App 现状
> 关联: 后端 Super Individual 7 大能力已全部合入 master

---

## 一、现状对比总览

### 1.1 导航结构差异

| 维度 | 设计稿 (Stitch) | Android 现状 | 差距 |
|------|----------------|-------------|------|
| 底部 Tab 数 | 4 个 | 5 个 | 结构不一致 |
| Tab 定义 | Chat, Assets, Status, Settings | Home, Tasks, Projects, Account, Artifacts | 命名和分组均不同 |
| 核心交互范式 | **对话驱动** (Chat-centric) | **任务驱动** (Task-centric) | 范式级差异 |

### 1.2 功能覆盖矩阵

| 设计稿功能 | 设计稿描述 | Android 现状 | 差距等级 |
|-----------|-----------|-------------|---------|
| 对话式 AI 交互 | 气泡消息、建议芯片、浮动输入框 | 无 — 仅有简单文本输入 + 发送按钮 | 🔴 缺失 |
| 可视化流水线步进器 | 5 步 Pipeline Stepper + 实时状态 | 单一 LinearProgressIndicator + 百分比 | 🔴 缺失 |
| 实时日志控制台 | 内嵌式日志流、构建洞察 | 事件列表 (AgentEventItem) | 🟡 部分 |
| 审批卡片 | 待审批卡片 + 同意/拒绝按钮 | ApprovalBottomSheet (倒计时 + 评论) | 🟢 已实现 |
| 资产中心 | Bento 网格、存储统计、AI 洞察 | ArtifactHub + ArtifactDetail + 发布流程 | 🟢 已实现 |
| 状态监控屏 | 资源利用率、平均执行时间、成功率 | 无独立 Status 页面 | 🔴 缺失 |
| 账户绑定 | GitHub/Google/Slack/Notion 集成 | 仅 BaseURL + 生成目标 + Agent 配置 | 🔴 缺失 |
| 系统健康指标 | CPU/内存/磁盘使用率 | 无 | 🔴 缺失 |
| 网络拓扑图 | SVG 可视化网络连接 | 无 | 🔴 缺失 |
| 配额/额度显示 | Credits 进度条 | 无 | 🔴 缺失 |
| 登录页 | 邮箱/密码 + Google/Apple 社交登录 | 无登录页 (直接 Token) | 🟡 待定 |
| 暗色主题 | Sentinel 暗色主题 | Material3 动态主题 | 🟢 已实现 |

### 1.3 Super Individual 新事件 UI 适配

后端新增的 8 种事件已在 Android 中全部接线：

| 事件 | UI 渲染 | 与设计稿对齐 |
|------|--------|-------------|
| CLARIFICATION_REQUESTED | 问题卡片 + 选项列表 | 🟡 需要交互式选择组件 |
| CLARIFICATION_ANSWERED | 回答展示卡片 | 🟢 |
| REPO_BOOTSTRAP_STARTED | 加载指示器 + URL | 🟢 |
| REPO_BOOTSTRAP_DONE | 文件数 + 依赖状态 | 🟢 |
| CODE_INDEX_BUILT | 文件数 + 符号数 + 摘要 | 🟢 |
| PLAN_APPROVAL_REQUESTED | 方案摘要 + 步骤列表 + 审批按钮 | 🟢 对齐设计稿审批卡 |
| TEST_GENERATED | 测试文件 + 数量 + 框架 | 🟢 |
| KNOWLEDGE_WRITEBACK | 知识存储统计 | 🟢 |

---

## 二、升级优先级矩阵

### P0 — 核心体验 (必须做)

| # | 改进项 | 设计稿参考 | 当前状态 | 工作量估估 |
|---|--------|-----------|---------|----------|
| 1 | **对话式聊天界面** | `67013b72` Chat 屏 | 无 | 大 |
| 2 | **流水线步进器组件** | `090d5e38` Task Detail 屏 | 无 | 中 |
| 3 | **导航重构 4-Tab** | 所有屏底部导航 | 5-Tab 结构 | 中 |
| 4 | **CLARIFICATION_REQUESTED 交互** | 设计稿审批卡模式 | 静态展示 | 小 |

### P1 — 功能完善 (应该做)

| # | 改进项 | 设计稿参考 | 当前状态 | 工作量估 |
|---|--------|-----------|---------|---------|
| 5 | **独立状态监控页** | `4cab0d25` Status 屏 | 无 | 中 |
| 6 | **实时日志流组件** | `090d5e38` 控制台区域 | 事件列表 | 中 |
| 7 | **任务创建对话流** | `e8dc7bd8` Home 屏 | 简单输入框 | 中 |
| 8 | **资产 Bento 网格** | `0cb07d75` Assets Hub | 列表视图 | 小 |

### P2 — 体验增强 (可以做)

| # | 改进项 | 设计稿参考 | 当前状态 | 工作量估 |
|---|--------|-----------|---------|---------|
| 9 | 账户绑定 UI | `7193b8b7` Settings 屏 | 无 | 中 |
| 10 | 系统健康仪表盘 | `7193b8b7` 健康指标区 | 无 | 小 |
| 11 | 配额/额度显示 | `7193b8b7` Credits 条 | 无 | 小 |
| 12 | 网络拓扑可视化 | `7ddb879ea9` 拓扑 SVG | 无 | 大 |
| 13 | 建议芯片 (Suggestion Chips) | `67013b72` 对话区 | 无 | 小 |

---

## 三、详细升级方案

### 3.1 P0-1: 对话式聊天界面

**目标**: 将核心交互从"填写表单 → 提交任务"转变为"自然语言对话 → Agent 响应"

**设计稿参考**: `67013b72` — AI 对话气泡 + 任务卡片网格 + 浮动输入框

**实现方案**:

```
┌─────────────────────────────┐
│  Chat Tab                   │
│  ┌───────────────────────┐  │
│  │ Agent 消息气泡         │  │
│  │ "我可以帮你做什么？"    │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ 用户消息气泡           │  │
│  │ "给文章列表加分页"      │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ 任务卡片 (嵌入对话)     │  │
│  │ ▓▓▓▓░░ 60%            │  │
│  │ CoderAgent 执行中...   │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ [输入消息...]    [发送] │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

**数据模型新增**:

```kotlin
data class ChatMessage(
    val id: String,
    val role: MessageRole,  // USER, ASSISTANT, SYSTEM
    val content: String,
    val timestamp: Instant,
    val embeddedTask: TaskItem? = null,  // 任务卡片嵌入
    val clarificationRequest: ClarificationRequest? = null,
    val approvalRequest: ApprovalRequest? = null,
)

enum class MessageRole { USER, ASSISTANT, SYSTEM }
```

**后端对接**:
- 现有 WebSocket/STOMP 通道 `/topic/tasks/{taskId}` 已支持事件流
- 需新增: 对话消息持久化 API (`POST /api/chat/messages`)
- CLARIFICATION_REQUESTED 事件直接嵌入为交互式消息卡片

---

### 3.2 P0-2: 流水线步进器组件

**目标**: 用可视化 5 步进度条替代单一百分比进度条

**设计稿参考**: `090d5e38` — Intent → Plan → Code → Review → Test

**实现方案**:

```
┌─────────────────────────────────────┐
│  ●───●───●───○───○                  │
│  意图  方案  编码  审查  测试         │
│                                      │
│  当前阶段: 编码                      │
│  Agent: CoderAgent                   │
│  耗时: 2m 30s                        │
└─────────────────────────────────────┘
```

**组件设计**:

```kotlin
@Composable
fun PipelineStepper(
    currentStage: PipelineStage,
    stages: List<StageInfo>,
    modifier: Modifier = Modifier
)

data class StageInfo(
    val stage: PipelineStage,
    val label: String,
    val status: StageStatus,  // PENDING, ACTIVE, COMPLETED, FAILED
    val duration: Duration? = null,
    val agent: String? = null,
)

enum class PipelineStage {
    BOOTSTRAP,   // 新: RepoBootstrap
    INDEX,       // 新: CodeIndex
    CLARIFY,     // 新: DialogueManager
    INTENT,
    PLAN,
    CODE,
    REVIEW,
    TEST,
    KNOWLEDGE,   // 新: KnowledgeExtractor
}
```

**事件映射**:

| 事件 | 步进器状态变化 |
|------|--------------|
| REPO_BOOTSTRAP_STARTED | BOOTSTRAP → ACTIVE |
| REPO_BOOTSTRAP_DONE | BOOTSTRAP → COMPLETED |
| CODE_INDEX_BUILT | INDEX → COMPLETED |
| CLARIFICATION_REQUESTED | CLARIFY → ACTIVE |
| TASK_STARTED | INTENT → ACTIVE |
| SPEC_PROPOSED | PLAN → COMPLETED |
| FILE_PATCH_PREVIEW | CODE → ACTIVE |
| BUILD_STARTED | REVIEW → ACTIVE |
| TEST_GENERATED | TEST → COMPLETED |
| KNOWLEDGE_WRITEBACK | KNOWLEDGE → COMPLETED |
| TASK_DONE | 全部 → COMPLETED |
| TASK_FAILED | 当前 → FAILED |

---

### 3.3 P0-3: 导航重构

**目标**: 从 5-Tab 改为 4-Tab，对齐设计稿

**当前 → 目标**:

```
当前 (5-Tab):          目标 (4-Tab):
┌────┬────┬────┐      ┌────┬────┬────┬────┐
│Home│Task│Proj│      │Chat│Asset│Status│Set│
│    │ s  │ects│      │    │  s  │      │tin│
├────┼────┼────┤      ├────┼────┼────┼────┤
│Acc │Art │    │      │    │    │    │    │
│ount│ifact│   │      │    │    │    │    │
└────┴────┴────┘      └────┴────┴────┴────┘
```

**合并策略**:

| 原 Tab | 去向 | 理由 |
|--------|------|------|
| Home | 合入 Chat | Home 的快速输入 → Chat 的对话入口 |
| Tasks | 合入 Chat | 任务列表 → Chat 中的任务卡片网格 |
| Projects | 合入 Assets | 项目 → 资产的一种类型 |
| Account | 改名 Settings | 对齐设计稿 |
| Artifacts | 改名 Assets | 对齐设计稿 |

---

### 3.4 P0-4: CLARIFICATION_REQUESTED 交互

**目标**: 将静态展示改为可交互的选择组件

**当前**: 仅显示问题文本和选项列表（只读）
**目标**: 用户可以点击选项或输入自定义回答，触发 CLARIFICATION_ANSWERED 事件

**实现**:

```kotlin
@Composable
fun ClarificationCard(
    request: ClarificationRequest,
    onAnswer: (String) -> Unit
) {
    Card {
        Text(request.question)
        request.options?.forEach { option ->
            Button(onClick = { onAnswer(option) }) {
                Text(option)
            }
        }
        var customAnswer by remember { mutableStateOf("") }
        OutlinedTextField(
            value = customAnswer,
            onValueChange = { customAnswer = it },
            label = { Text("自定义回答") }
        )
        Button(
            onClick = { onAnswer(customAnswer) },
            enabled = customAnswer.isNotBlank()
        ) {
            Text("发送")
        }
    }
}
```

---

### 3.5 P1-5: 独立状态监控页

**设计稿参考**: `4cab0d25` — Pipeline Stepper + 资源图表 + 执行统计

**内容**:
- 全局 Pipeline Stepper (当前活跃任务)
- 资源利用率图表 (CPU/内存 — 需后端 Prometheus API)
- 平均执行时间统计
- 成功率统计
- 最近日志流

**后端需求**:
- 新增 API: `GET /api/metrics/overview` — 返回系统级指标
- 现有 Prometheus 端点可复用

---

## 四、后端 API 需求清单

| # | API | 方法 | 用途 | 优先级 |
|---|-----|------|------|--------|
| 1 | `/api/chat/messages` | POST | 发送对话消息 | P0 |
| 2 | `/api/chat/messages` | GET | 获取对话历史 | P0 |
| 3 | `/api/chat/messages/{id}/reply` | POST | 回复澄清问题 | P0 |
| 4 | `/api/metrics/overview` | GET | 系统级指标 | P1 |
| 5 | `/api/tasks/{id}/pipeline` | GET | 流水线阶段详情 | P0 |
| 6 | `/api/accounts/bindings` | GET/POST | 账户绑定管理 | P2 |
| 7 | `/api/credits/balance` | GET | 配额余额 | P2 |

---

## 五、实施建议

### 5.1 分支策略

```
master
  ├── feat/frontend-chat-ui          ← P0-1 对话界面
  ├── feat/frontend-pipeline-stepper ← P0-2 步进器
  ├── feat/frontend-nav-refactor     ← P0-3 导航重构
  └── feat/frontend-status-monitor   ← P1-5 状态监控
```

### 5.2 建议执行顺序

1. **导航重构** (P0-3) — 先定框架，其他组件挂载到新 Tab 上
2. **流水线步进器** (P0-2) — 独立组件，可复用于 Chat 和 Status 页
3. **对话界面** (P0-1) — 核心体验，依赖步进器组件
4. **CLARIFICATION 交互** (P0-4) — 对话界面的子功能
5. **状态监控页** (P1-5) — 独立页面，可并行开发

### 5.3 预估工时

| 阶段 | 工时 | 产出 |
|------|------|------|
| P0 全部 | 5-7 天 | 核心体验对齐设计稿 |
| P1 全部 | 3-4 天 | 功能完善 |
| P2 全部 | 3-5 天 | 体验增强 |
| **总计** | **11-16 天** | 完全对齐设计稿 |

---

## 六、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 对话界面需要后端消息持久化 API | P0-1 阻塞 | 先用本地 Room 数据库，后端 API 后续接入 |
| 流水线步进器阶段定义可能变化 | P0-2 返工 | 设计为可配置阶段列表，非硬编码 |
| 导航重构影响面大 | P0-3 回归风险 | Feature Flag 控制新旧导航切换 |
| 设计稿截图无交互细节 | 实现偏差 | 以设计稿 HTML 源码为准，截图仅参考 |
