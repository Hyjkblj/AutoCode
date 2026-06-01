# 移动端 App 升级计划

> 生成日期: 2026-05-27
> 基准: `mobile-app/` 现有代码 + `docs/stitch/upgraded-ui-design/` 设计稿
> 目标: 将 Android App 从"任务驱动 5-Tab"升级为"对话驱动 4-Tab"，对齐设计稿

---

## 一、现状审计

### 1.1 代码结构

| 文件 | 行数 | 职责 | 问题 |
|------|------|------|------|
| `AppUi.kt` | ~2540 | **全部 UI** — 导航、所有页面、所有组件 | 🔴 单文件巨石，不可维护 |
| `AppViewModel.kt` | ~2346 | **全部业务逻辑** — 网络、持久化、状态管理 | 🔴 单文件巨石 |
| `Models.kt` | 189 | 数据模型 | 🟢 结构清晰 |
| `EventDto.kt` | 28 | 事件常量 | 🟢 |
| `Theme.kt` | 22 | 主题 (仅亮色) | 🔴 无暗色主题、无设计系统 |
| `MainActivity.kt` | 45 | 入口 | 🟢 |
| `network/ControlPlaneClient.kt` | — | REST 客户端 | 🟢 |
| `network/WebSocketClient.kt` | — | WebSocket 客户端 | 🟢 |

### 1.2 导航结构 (当前 vs 目标)

```
当前 (5-Tab):              目标 (4-Tab, 设计稿):
┌──────┬──────┬──────┐    ┌──────┬──────┬──────┬──────┐
│ Home │Tasks │ Art  │    │ Chat │Assets│Status│Config│
├──────┼──────┼──────┤    ├──────┼──────┼──────┼──────┤
│ Proj │Acct  │      │    │      │      │      │      │
└──────┴──────┴──────┘    └──────┴──────┴──────┴──────┘
```

### 1.3 主题系统 (当前 vs 目标)

| 维度 | 当前 | 设计稿 |
|------|------|--------|
| 色彩方案 | 蓝色 `#2F95DC` 单一亮色 | Amber Intelligence 琥珀色系 |
| 暗色模式 | ❌ 无 | ✅ 暗色主题 (Status/Detail 屏) |
| 字体 | M3 默认 | Public Sans (400-900) |
| 卡片风格 | 默认 M3 Card | Glass Panel + Bento Grid |
| 圆角 | M3 默认 | 大圆角 (2xl/3xl) |

### 1.4 组件清单 (当前)

| 组件 | 位置 | 状态 |
|------|------|------|
| `AgentEventItem` | AppUi.kt:712 | 能用，但内联了 16+ 事件的渲染逻辑 |
| `ApprovalBottomSheet` | AppUi.kt:1368 | 🟢 功能完整 |
| `FixLoopTimelineCard` | AppUi.kt:1332 | 🟢 |
| `VoiceInputButton` | AppUi.kt:536 | 🟢 |
| `ArtifactPreviewCard` | AppUi.kt:1946 | 🟢 |
| `DeployStatusCard` | AppUi.kt:2026 | 🟢 |
| Pipeline Stepper | ❌ 不存在 | 需新建 |
| Chat Bubble | ❌ 不存在 | 需新建 |
| Clarification Card | ❌ 不存在 (仅静态展示) | 需新建交互版 |
| Code Index Summary Card | ❌ 不存在 | 需新建 |
| Event Timeline | ❌ 不存在 (仅列表) | 需新建 |
| Resource Utilization Chart | ❌ 不存在 | 需新建 |
| System Health Grid | ❌ 不存在 | 需新建 |

---

## 二、升级任务清单

### Phase 0: 基础设施 (必须先做)

#### T0.1: 主题系统重构

**文件**: `ui/theme/Theme.kt`, `ui/theme/Color.kt`, `ui/theme/Type.kt` (新建)

**当前**: 22 行，仅 `lightColorScheme`，蓝色主色
**目标**: Amber Intelligence 色系，亮/暗双主题

```kotlin
// Color.kt
val AmberPrimary = Color(0xFF855300)
val AmberPrimaryContainer = Color(0xFFF59E0B)
val AmberOnPrimary = Color(0xFFFFFFFF)
val AmberSurface = Color(0xFFFFF8F4)
val AmberBackground = Color(0xFFFFF8F4)

// 暗色
val AmberDarkPrimary = Color(0xFFFFC174)
val AmberDarkBackground = Color(0xFF161311)
val AmberDarkSurface = Color(0xFF1E1B18)
```

**验收**: 切换亮/暗色主题，所有页面颜色正确

---

#### T0.2: AppUi.kt 拆分

**当前**: 单文件 2540 行
**目标**: 按页面/组件拆分

```
mobile-app/app/src/main/kotlin/com/autocode/mobile/
├── AppViewModel.kt          (保持，后续拆分)
├── Models.kt                (保持)
├── MainActivity.kt          (保持)
├── EventDto.kt              (保持)
├── ui/
│   ├── theme/
│   │   ├── Theme.kt         (重构)
│   │   ├── Color.kt         (新建)
│   │   └── Type.kt          (新建)
│   ├── navigation/
│   │   └── AppNavigation.kt (新建 — 导航图)
│   ├── screens/
│   │   ├── LoginScreen.kt   (从 AppUi.kt 提取)
│   │   ├── ChatScreen.kt    (新建)
│   │   ├── AssetsScreen.kt  (从 ArtifactsHubTab 提取)
│   │   ├── StatusScreen.kt  (新建)
│   │   ├── SettingsScreen.kt (从 AccountTab 提取)
│   │   └── TaskDetailScreen.kt (从 TaskDetailTab 提取)
│   └── components/
│       ├── PipelineStepper.kt     (新建)
│       ├── ChatBubble.kt          (新建)
│       ├── ClarificationCard.kt   (新建)
│       ├── CodeIndexCard.kt       (新建)
│       ├── EventTimeline.kt       (新建)
│       ├── ApprovalCard.kt        (从 ApprovalBottomSheet 提取)
│       ├── AgentEventItem.kt      (从 AppUi.kt 提取)
│       └── BottomNavBar.kt        (新建)
└── network/                 (保持不变)
```

**验收**: 编译通过，功能无回归

---

#### T0.3: 导航重构

**当前**: 5-Tab (Home, Tasks, Artifacts, Projects, Account)
**目标**: 4-Tab (Chat, Assets, Status, Settings)

**合并策略**:

| 原 Tab | 去向 | 具体操作 |
|--------|------|---------|
| Home | 合入 Chat | HomeTab 的状态摘要 → ChatScreen 顶部 |
| Tasks | 合入 Chat | TaskListTab → ChatScreen 的任务列表视图 |
| Projects | 合入 Assets | ProjectsTab → AssetsScreen 的项目筛选 |
| Artifacts | 改名 Assets | 重命名 |
| Account | 改名 Settings | 重命名 + 扩展 |

**新建**: `StatusScreen.kt` — 系统监控仪表盘

**验收**: 底部 4 个 Tab 正确切换，所有原有功能可达

---

### Phase 1: 核心组件 (P0)

#### T1.1: PipelineStepper 组件

**新建**: `ui/components/PipelineStepper.kt`

**设计稿参考**: `task-detail-pipeline.html` — 9 步竖向步进器

```kotlin
@Composable
fun PipelineStepper(
    stages: List<PipelineStageInfo>,
    modifier: Modifier = Modifier
)

data class PipelineStageInfo(
    val stage: PipelineStage,
    val label: String,
    val status: StageStatus,  // COMPLETED, ACTIVE, SKIPPED, PENDING
    val duration: Duration? = null,
    val detail: String? = null,
)

enum class PipelineStage {
    BOOTSTRAP, INDEX, CLARIFY, INTENT, PLAN, CODE, REVIEW, TEST, KNOWLEDGE
}
```

**验收**: 在 TaskDetailScreen 中正确显示 9 步进度

---

#### T1.2: ChatScreen 对话界面

**新建**: `ui/screens/ChatScreen.kt`

**设计稿参考**: `chat-with-pipeline.html`

**功能**:
- 对话消息列表 (LazyColumn)
- 气泡消息 (用户/Agent)
- 嵌入式任务卡片
- 澄清交互卡片
- 审批卡片
- 测试结果卡片
- 代码索引摘要卡片
- 事件时间线
- 底部输入框 + 发送按钮

**数据模型新增**:

```kotlin
data class ChatMessage(
    val id: String,
    val role: MessageRole,  // USER, ASSISTANT, SYSTEM
    val content: String,
    val timestamp: Instant,
    val embeddedTask: TaskItem? = null,
    val clarificationRequest: ClarificationRequest? = null,
    val planApproval: PlanApprovalRequest? = null,
    val testResult: TestGeneratedInfo? = null,
    val codeIndex: CodeIndexInfo? = null,
)

enum class MessageRole { USER, ASSISTANT, SYSTEM }
```

**验收**: 可发送消息，Agent 回复正确渲染，嵌入卡片可交互

---

#### T1.3: ClarificationCard 交互组件

**新建**: `ui/components/ClarificationCard.kt`

**当前**: AgentEventItem 中仅静态展示问题文本
**目标**: 可点击选项、可输入自定义回答、触发 CLARIFICATION_ANSWERED 事件

```kotlin
@Composable
fun ClarificationCard(
    request: ClarificationRequest,
    onAnswer: (String) -> Unit,
    modifier: Modifier = Modifier
)
```

**验收**: 点击选项按钮触发 onAnswer，自定义输入可发送

---

#### T1.4: CodeIndexCard 摘要组件

**新建**: `ui/components/CodeIndexCard.kt`

**设计稿参考**: `chat-with-pipeline.html` — 代码索引摘要卡片

```kotlin
@Composable
fun CodeIndexCard(
    info: CodeIndexInfo,
    modifier: Modifier = Modifier
)
```

**验收**: 显示文件数、符号数、摘要文本

---

#### T1.5: EventTimeline 组件

**新建**: `ui/components/EventTimeline.kt`

**设计稿参考**: `chat-with-pipeline.html` — 事件流时间线

```kotlin
@Composable
fun EventTimeline(
    events: List<TimelineEvent>,
    modifier: Modifier = Modifier
)

data class TimelineEvent(
    val timestamp: Instant,
    val type: String,
    val description: String,
    val status: EventStatus,  // SUCCESS, ACTIVE, PENDING
)
```

**验收**: 事件按时间排列，状态颜色正确

---

### Phase 2: 页面升级 (P1)

#### T2.1: TaskDetailScreen 重构

**当前**: TaskDetailTab — 事件列表 + 审批表
**目标**: 9 步 Pipeline 步进器 + 实时日志 + 文件变更预览 + Agent 状态

**设计稿参考**: `task-detail-pipeline.html`

**改动点**:
1. 顶部添加 PipelineStepper
2. 事件列表改为 EventTimeline
3. 添加实时日志控制台 (可折叠)
4. 添加文件变更预览区
5. Agent 状态卡片

**验收**: 所有事件类型正确渲染，审批流程正常

---

#### T2.2: StatusScreen 新建

**新建**: `ui/screens/StatusScreen.kt`

**设计稿参考**: `status-monitor.html`

**功能**:
- 活跃任务列表 (带 Pipeline 进度条)
- 统计卡片 (成功率、平均执行时间)
- 资源利用率 (CPU/内存/磁盘 — 需后端 API)
- 最近事件流
- 系统健康指示器

**后端需求**:
- `GET /api/metrics/overview` — 系统级指标 (可选，先用 mock 数据)

**验收**: 页面正确显示，数据从 ViewModel 获取

---

#### T2.3: SettingsScreen 重构

**当前**: AccountTab — baseUrl + 生成目标 + Agent 配置 + 通知开关
**目标**: 对齐设计稿 Settings 屏 — 个人资料 + 绑定 + 偏好 + 系统健康

**设计稿参考**: `7193b8b7` (Settings 屏)

**新增**:
- 个人资料卡片 (头像 + 名称 + 邮箱)
- 账户绑定区 (GitHub/Google — 占位)
- 语言/主题切换
- 配额/额度显示 (占位)
- 系统健康指标

**验收**: 所有设置项可操作

---

### Phase 3: 体验增强 (P2)

#### T3.1: 暗色主题适配

**当前**: 仅亮色主题
**目标**: 亮/暗双主题，跟随系统设置

**改动点**:
- Theme.kt 添加 `darkColorScheme`
- 所有硬编码颜色替换为主题 token
- Glass Panel 效果在暗色下的适配

**验收**: 系统切换暗色模式，App 正确跟随

---

#### T3.2: ChatScreen 任务创建流

**当前**: TaskListTab 中的文本输入框 → 直接创建任务
**目标**: 对话式创建 — 用户输入需求 → Agent 追问 → 确认 → 创建

**流程**:
1. 用户在 ChatScreen 输入需求
2. Agent (DialogueManager) 判断是否需要澄清
3. 如需要 → 显示 ClarificationCard
4. 用户回答 → Agent 确认 → 创建任务
5. 任务卡片嵌入对话流

**验收**: 完整对话创建流程

---

#### T3.3: AgentEventItem 重构

**当前**: AppUi.kt:712 — 单个 `when` 块处理 16+ 事件类型
**目标**: 拆分为独立组件，每种事件类型一个渲染函数

```
ui/components/events/
├── AssistantOutputEvent.kt
├── ToolStartEndEvent.kt
├── FilePatchPreviewEvent.kt
├── ApprovalRequiredEvent.kt
├── ClarificationEvent.kt
├── RepoBootstrapEvent.kt
├── CodeIndexEvent.kt
├── PlanApprovalEvent.kt
├── TestGeneratedEvent.kt
├── KnowledgeWritebackEvent.kt
└── EventItemRouter.kt  (when 分发)
```

**验收**: 所有事件类型渲染不变，代码可维护

---

## 三、依赖关系

```
Phase 0 (基础):
  T0.1 主题 ──┐
  T0.2 拆分 ──┼── T0.3 导航
              │
Phase 1 (组件):  依赖 Phase 0
  T1.1 PipelineStepper ──┐
  T1.2 ChatScreen ───────┼── T2.1 TaskDetail 重构
  T1.3 ClarificationCard ┤
  T1.4 CodeIndexCard ────┤
  T1.5 EventTimeline ────┘
                          │
Phase 2 (页面):  依赖 Phase 1
  T2.1 TaskDetail ────────┤
  T2.2 StatusScreen ──────┤
  T2.3 SettingsScreen ────┘
                          │
Phase 3 (增强):  依赖 Phase 2
  T3.1 暗色主题
  T3.2 对话创建流
  T3.3 EventItem 重构
```

---

## 四、文件变更矩阵

| 文件 | 操作 | Phase |
|------|------|-------|
| `ui/theme/Theme.kt` | 重构 | 0 |
| `ui/theme/Color.kt` | 新建 | 0 |
| `ui/theme/Type.kt` | 新建 | 0 |
| `ui/navigation/AppNavigation.kt` | 新建 | 0 |
| `ui/screens/ChatScreen.kt` | 新建 | 1 |
| `ui/screens/StatusScreen.kt` | 新建 | 2 |
| `ui/screens/SettingsScreen.kt` | 从 AccountTab 提取 | 2 |
| `ui/screens/LoginScreen.kt` | 从 AppUi.kt 提取 | 0 |
| `ui/screens/AssetsScreen.kt` | 从 ArtifactsHubTab 提取 | 0 |
| `ui/screens/TaskDetailScreen.kt` | 从 TaskDetailTab 提取 | 0 |
| `ui/components/PipelineStepper.kt` | 新建 | 1 |
| `ui/components/ChatBubble.kt` | 新建 | 1 |
| `ui/components/ClarificationCard.kt` | 新建 | 1 |
| `ui/components/CodeIndexCard.kt` | 新建 | 1 |
| `ui/components/EventTimeline.kt` | 新建 | 1 |
| `ui/components/ApprovalCard.kt` | 从 AppUi.kt 提取 | 0 |
| `ui/components/AgentEventItem.kt` | 从 AppUi.kt 提取 | 0 |
| `ui/components/BottomNavBar.kt` | 新建 | 0 |
| `ui/components/events/*.kt` | 新建 (10 文件) | 3 |
| `Models.kt` | 新增 ChatMessage 等 | 1 |
| `AppUi.kt` | 删除 (拆分后) | 0 |
| `AppViewModel.kt` | 新增对话/状态相关方法 | 1-2 |

---

## 五、工时估算

| Phase | 任务数 | 工时 | 产出 |
|-------|--------|------|------|
| Phase 0 | 3 | 3-4 天 | 主题系统 + 代码拆分 + 导航重构 |
| Phase 1 | 5 | 4-5 天 | 5 个核心组件 |
| Phase 2 | 3 | 3-4 天 | 3 个页面升级/新建 |
| Phase 3 | 3 | 2-3 天 | 暗色主题 + 对话流 + 事件重构 |
| **总计** | **14** | **12-16 天** | 完全对齐设计稿 |

---

## 六、风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| AppUi.kt 拆分可能引入回归 | 高 | 逐函数提取，每步编译验证 |
| 对话界面需要后端消息 API | 中 | 先用本地 Room 存储，后端 API 后续接入 |
| StatusScreen 需要后端指标 API | 低 | 先用 mock 数据，API 就绪后替换 |
| 暗色主题下 Glass Panel 效果 | 低 | 使用 Compose `drawBehind` 自定义 |
