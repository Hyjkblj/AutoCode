
# 赛题 2 超级个体 — 实施方案

> 生成日期: 2026-05-13
> 目标仓库: gothinkster/react-redux-realworld-example-app (TypeScript + React + Redux + Express)
> 交互界面: 沿用现有 Android App (Kotlin/Jetpack Compose)
> 开发周期: 3 周

---

## 一、项目背景

### 1.1 赛题要求

实现一个可以端到端交付全栈项目的"超级个体"，使用 Conduit (RealWorld) React Redux 仓库作为测试平台，完成：

**PM 对话流程**：需求澄清 → 方案拆解 → 模块定位 → 代码生成 → 自动化测试 → 代码部署

**核心要求**：
- 每个阶段可以人工介入
- 最终产出可提测代码并实现知识回写
- 3 周内完成

### 1.2 AutoCode 现状分析

**已有优势**：
- 5-Agent 编排引擎 (IntentAgent → PlannerAgent → CoderAgent → ReviewerAgent → TesterAgent)
- DAG 并行执行调度器
- 18 种事件协议 + 状态机
- 审批机制 (APPROVAL_REQUIRED → APPROVAL_RESULT)
- Fix Loop 修复循环
- Plugin 系统 + CircuitBreaker
- Android App 实时事件流

**7 大差距**：

| # | 差距 | 影响 |
|---|------|------|
| 1 | 无 Git 操作能力 | 无法克隆仓库、提交代码 |
| 2 | 无代码索引 | 无法理解仓库结构和模块关系 |
| 3 | 无多轮对话 | 无法进行需求澄清 |
| 4 | 无增量代码修改 | 只能从零生成，无法修改已有代码 |
| 5 | 无测试生成 | 无法自动生成单元测试 |
| 6 | 无全阶段人工介入 | 只有代码执行阶段有审批 |
| 7 | 无知识回写 | 任务间无法复用经验 |

---

## 二、目标仓库分析

### 2.1 Conduit (RealWorld) 仓库结构

```
react-redux-realworld-example-app/
├── src/
│   ├── agent.ts                 # API 客户端
│   ├── components/              # React 组件
│   │   ├── Article/             # 文章详情
│   │   ├── ArticleList/         # 文章列表
│   │   ├── Comment/             # 评论
│   │   ├── Editor/              # 编辑器
│   │   ├── Home/                # 首页
│   │   ├── Login/               # 登录
│   │   ├── Profile/             # 个人主页
│   │   ├── Register/            # 注册
│   │   ├── Settings/            # 设置
│   │   └── Shared/              # 共享组件
│   ├── constants/               # 常量
│   ├── middleware/              # Redux 中间件
│   ├── reducer/                 # Redux Reducer
│   │   ├── article.ts
│   │   ├── articleList.ts
│   │   ├── auth.ts
│   │   ├── comment.ts
│   │   ├── common.ts
│   │   ├── editor.ts
│   │   ├── home.ts
│   │   ├── profile.ts
│   │   └── settings.ts
│   └── store.ts                 # Redux Store
├── package.json
├── tsconfig.json
└── webpack.config.js
```

### 2.2 6 大业务领域

| 领域 | 涉及组件 | 涉及 Reducer |
|------|----------|--------------|
| Auth | Login, Register | auth.ts |
| Articles | Article, ArticleList, Editor | article.ts, articleList.ts |
| Comments | Comment | comment.ts |
| Favorites | Home (favorite 功能) | home.ts |
| Profiles | Profile | profile.ts |
| Tags | Home (tag 功能) | home.ts |

---

## 三、技术方案设计

### 3.1 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      Android App                            │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ 澄清对话 │ │ 方案审批  │ │ 代码预览 │ │ 测试结果        │  │
│  └─────────┘ └──────────┘ └─────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │ Event Protocol
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Control Plane (Java)                       │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │TaskService│ │EventStore│ │Approval │ │ StateMachine    │  │
│  └─────────┘ └──────────┘ └─────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │ REST API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python Agent (新增)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              AgentOrchestrator (扩展)                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │   │
│  │  │RepoBootstrap│ │CodeIndex│ │DialogueMgr│            │   │
│  │  └──────────┘ └──────────┘ └──────────┘             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │   │
│  │  │GitTool   │ │HumanGate │ │Knowledge │             │   │
│  │  └──────────┘ └──────────┘ └──────────┘             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Existing Agents (重构)                   │   │
│  │  IntentAgent → PlannerAgent → CoderAgent → Tester    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Conduit Workspace                          │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ Git Repo │ │ CodeIndex│ │ Tests  │ │ node_modules    │  │
│  └─────────┘ └──────────┘ └─────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 新增组件清单

#### Python 端 (7 个新文件)

| 文件 | 职责 | 核心方法 |
|------|------|----------|
| `tools/git_tool.py` | Git 操作 | clone, checkout_branch, add, commit, push, diff, status |
| `tools/code_index.py` | 代码索引 | scan, find_symbol, get_dependents, to_context_summary |
| `tools/repo_bootstrap.py` | 仓库引导 | bootstrap, install_dependencies |
| `agents/dialogue_manager.py` | 多轮对话 | needs_clarification, incorporate_clarification |
| `generators/test_generator.py` | 测试生成 | detect_test_framework, generate_tests |
| `plugins/human_gate.py` | 人工门控 | request_approval, check_approval, should_gate |
| `memory/knowledge_extractor.py` | 知识提取 | extract_file_summary, extract_project_architecture |

#### Python 端 (6 个修改文件)

| 文件 | 修改点 |
|------|--------|
| `orchestrator/agent_orchestrator.py` | __init__ 注入新组件, _handle_task_locked 插入新阶段 |
| `agents/coder_agent.py` | 增量修改重构 (L379, L403, L47) |
| `agents/tester_agent.py` | 集成测试生成 |
| `memory/redis_memory.py` | 新增知识存储方法 |
| `generators/validation_gate.py` | TS/React/Express 校验 |
| `generators/fix_loop.py` | TS 错误修复策略 |
| `main.py` | 接线新组件 |

#### Java 端 (9 个新事件 + 9 个 Payload)

**新事件类型**：
```
CLARIFICATION_REQUESTED   — Agent 追问
CLARIFICATION_ANSWERED    — 用户回答
REPO_BOOTSTRAP_STARTED    — clone 开始
REPO_BOOTSTRAP_DONE       — workspace 就绪
CODE_INDEX_BUILT          — 索引完成
PLAN_APPROVAL_REQUESTED   — 方案待审批
TEST_GENERATED            — 测试已生成
KNOWLEDGE_WRITEBACK       — 知识已回写
```

**新 Payload 类**：
```
shared-protocol/.../payload/
├── ClarificationRequestedPayload.java
├── ClarificationAnsweredPayload.java
├── RepoBootstrapStartedPayload.java
├── RepoBootstrapDonePayload.java
├── CodeIndexBuiltPayload.java
├── PlanApprovalRequestedPayload.java
├── TestGeneratedPayload.java
└── KnowledgeWritebackPayload.java
```

---

## 四、3 周实施计划

### Week 1: 基础能力（Day 1-7）

**目标**：系统能克隆仓库、理解代码结构、多轮对话

#### Task 1.1: GitTool — Git 操作工具

**新建**: `python-agent/tools/git_tool.py`

```python
@dataclass(frozen=True)
class GitResult:
    ok: bool
    output: str
    exit_code: int | None
    error: str | None

class GitTool:
    def __init__(self, exec_tool: ExecTool | None = None, *, use_local_git: bool = False) -> None:
        self.exec_tool = exec_tool
        self.use_local_git = use_local_git or os.getenv("MVP_USE_LOCAL_GIT", "").strip().lower() in ("1", "true", "yes")

    def clone(self, repo_url: str, target_dir: str, *, branch: str = "", depth: int | None = None) -> GitResult: ...
    def checkout_branch(self, repo_dir: str, branch_name: str, *, create: bool = True) -> GitResult: ...
    def add(self, repo_dir: str, paths: list[str] | None = None) -> GitResult: ...
    def commit(self, repo_dir: str, message: str) -> GitResult: ...
    def push(self, repo_dir: str, branch: str = "", *, force: bool = False) -> GitResult: ...
    def status(self, repo_dir: str) -> GitResult: ...
    def diff(self, repo_dir: str, *, staged: bool = False) -> GitResult: ...
    def log(self, repo_dir: str, limit: int = 10) -> GitResult: ...
```

**实现要点**：
- 委托 `ExecTool.execute()` 执行 git 命令
- 本地开发 fallback: `subprocess.run` 模式（`use_local_git=True`）
- 突变操作 (commit/push) 走 `APPROVAL_REQUIRED` 审批

**验证**: clone Conduit 仓库，检查 `package.json` 存在

---

#### Task 1.2: CodeIndex — 代码索引

**新建**: `python-agent/tools/code_index.py`

```python
@dataclass(frozen=True)
class SymbolInfo:
    name: str
    kind: str
    file_path: str
    line: int
    signature: str

@dataclass(frozen=True)
class FileInfo:
    path: str
    language: str
    exports: list[str]
    imports: list[str]
    symbols: list[SymbolInfo]

class CodeIndex:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve(strict=False)
        self._files: dict[str, FileInfo] = {}
        self._symbol_index: dict[str, list[SymbolInfo]] = {}
        self._dependents: dict[str, set[str]] = {}

    def scan(self) -> None: ...
    def find_symbol(self, name: str) -> list[SymbolInfo]: ...
    def get_dependents(self, file_path: str) -> list[str]: ...
    def to_context_summary(self, *, max_files: int = 50) -> str: ...
```

**实现要点**：
- 基于正则解析 TS/JS（不引入 tree-sitter 重依赖）
- 提取: `export function/class/const/interface/type`, `import ... from`, `connect(`, `mapStateToProps`
- `to_context_summary()` 输出结构化文本供 LLM 使用，上限 ~3000 tokens

**验证**: 索引 Conduit 仓库，能发现 ArticleReducer、Home 组件、agent.ts API 客户端

---

#### Task 1.3: DialogueManager — 多轮对话

**新建**: `python-agent/agents/dialogue_manager.py`

```python
@dataclass
class ClarificationQuestion:
    question: str
    options: list[str] | None
    context: str
    stage: str

class DialogueManager:
    def __init__(self, llm_client: LLMClient | None = None) -> None: ...
    def needs_clarification(self, prompt: str, stage: str, context: dict) -> ClarificationQuestion | None: ...
    def incorporate_clarification(self, original_prompt: str, answer: str) -> str: ...
    def summarize_context(self, *, max_turns: int = 10) -> str: ...
```

**实现要点**：
- LLM 判断需求模糊度，高模糊时生成追问
- 澄清流程: 发射 `CLARIFICATION_REQUESTED` 事件 → 任务暂停 → 用户回复 → 合并继续

**验证**: 输入 "改进一下这个应用"，系统追问具体改什么

---

#### Task 1.4: RepoBootstrap — 仓库引导

**新建**: `python-agent/tools/repo_bootstrap.py`

```python
@dataclass(frozen=True)
class BootstrapResult:
    ok: bool
    repo_dir: str
    file_count: int
    dependencies_installed: bool
    error: str | None

class RepoBootstrap:
    def __init__(self, git_tool: GitTool, exec_tool: ExecTool | None = None) -> None: ...
    def bootstrap(self, repo_url: str, workspace_base: str, *, branch: str = "main") -> BootstrapResult: ...
    def install_dependencies(self, repo_dir: str) -> BootstrapResult: ...
```

**实现要点**：
- clone → npm install → 验证 package.json + node_modules
- 固定 commit hash 防止上游变更

**验证**: clone Conduit，`npm install` 成功，`node_modules` 存在

---

#### Task 1.5: 新增事件类型

**修改**: `shared-protocol/.../EventType.java`

新增 9 个事件类型:
```java
CLARIFICATION_REQUESTED,
CLARIFICATION_ANSWERED,
REPO_BOOTSTRAP_STARTED,
REPO_BOOTSTRAP_DONE,
CODE_INDEX_BUILT,
PLAN_APPROVAL_REQUESTED,
TEST_GENERATED,
KNOWLEDGE_WRITEBACK
```

**新建**: 对应 9 个 Payload 类

**修改**: `TaskService.java` L1133 `isInformationalEvent` — 将新事件加入信息事件

---

#### Task 1.6: Orchestrator 集成

**修改**: `python-agent/orchestrator/agent_orchestrator.py`

在 `__init__` 注入新组件:
```python
def __init__(self, ..., git_tool, code_index, dialogue_manager, repo_bootstrap): ...
```

在 `_handle_task_locked` 插入新阶段:
```
1. [NEW] 检查 task["repoUrl"] → RepoBootstrap.bootstrap()
2. [NEW] 构建 CodeIndex.scan() → 发射 CODE_INDEX_BUILT
3. [NEW] DialogueManager.needs_clarification() → 发射 CLARIFICATION_REQUESTED
4. [EXISTING] Memory context
5. [EXISTING] Intent inference
6. [EXISTING] Plan build
7. [EXISTING] Intent routing
```

**修改**: `python-agent/main.py` — 接线 GitTool、CodeIndex、DialogueManager、RepoBootstrap

**验证**: 发送带 `repoUrl` 的任务，clone + 索引 + 意图分类完整跑通

---

### Week 2: 核心流水线（Day 8-14）

**目标**：增量代码修改、测试生成、全阶段人工介入、知识回写

#### Task 2.1: CoderAgent 重构 — 增量修改

**修改**: `python-agent/agents/coder_agent.py`

注入依赖 (L24):
```python
def __init__(self, ..., code_index: CodeIndex | None = None, git_tool: GitTool | None = None): ...
```

替换核心方法:

1. `_choose_target_file` (L379) → `_resolve_target_files` 返回 `list[Path]`:
   - 有 CodeIndex: 用 LLM + 仓库上下文选择目标文件
   - 无 CodeIndex: fallback 到原逻辑

2. `_propose_content` (L403) → `_apply_incremental_edit`:
   - 始终用 LLM，注入仓库结构上下文 + 目标文件内容 + 修改请求
   - System prompt: "You are a precise code editor for React+Redux+TypeScript..."

3. `execute` (L47) → 支持多文件:
   - `_resolve_target_files()` → 循环 `_apply_incremental_edit()` → 写入 → 生成 unified diff → 发射 `FILE_PATCH_PREVIEW`

**验证**: 请求 "给文章列表加分页"，修改 ArticleList 组件而非 README

---

#### Task 2.2: TestGenerator — 测试生成

**新建**: `python-agent/generators/test_generator.py`

```python
@dataclass(frozen=True)
class GeneratedTest:
    file_path: str
    content: str
    framework: str
    test_count: int

class TestGenerator:
    def __init__(self, llm_client: LLMClient | None = None, code_index: CodeIndex | None = None): ...
    def detect_test_framework(self, workspace: Path) -> str: ...
    def generate_tests(self, workspace: Path, changed_files: list[str], prompt: str) -> list[GeneratedTest]: ...
```

**实现要点**：
- 检测 `package.json` devDependencies 确定框架 (jest/mocha/vitest)
- LLM 生成测试: 源文件内容 + 导入上下文 + 测试框架约定 + 已有测试模式

**修改**: `python-agent/agents/tester_agent.py`
- `execute()` 中: 检查变更文件是否有测试 → 无则调用 `TestGenerator` → 写入测试文件 → 执行测试命令

**验证**: CoderAgent 修改文件后，TesterAgent 自动生成测试并运行 `npm test`

---

#### Task 2.3: HumanGate — 全阶段人工门控

**新建**: `python-agent/plugins/human_gate.py`

```python
class PipelineStage(Enum):
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    DEPLOY = "deploy"

@dataclass(frozen=True)
class GateDecision:
    approved: bool
    feedback: str | None

class HumanGate:
    def __init__(self, client: ControlPlaneClient | None = None): ...
    def request_approval(self, task, stage: PipelineStage, summary: str, details: dict) -> str: ...
    def check_approval(self, approval_id: str, timeout_seconds: int = 300) -> GateDecision: ...
    def should_gate(self, stage: PipelineStage, task: dict) -> bool: ...
```

**实现要点**：
- 复用现有 `APPROVAL_REQUIRED` 事件协议
- 门控点可配置: `task["approvalStages"]` 或环境变量 `MVP_APPROVAL_STAGES=plan,code`

**修改**: `agent_orchestrator.py` `_handle_code_change` 插入门控:
```
PlannerAgent → [PLAN GATE] → CoderAgent → [CODE GATE] → ValidationGate → ReviewerAgent + TesterAgent
```

**验证**: 设置 `approvalStages: ["plan"]`，系统暂停在方案阶段等待审批

---

#### Task 2.4: KnowledgeExtractor — 知识回写

**新建**: `python-agent/memory/knowledge_extractor.py`

```python
class KnowledgeExtractor:
    def __init__(self, llm_client: LLMClient | None = None): ...
    def extract_file_summary(self, file_path: str, content: str) -> str: ...
    def extract_project_architecture(self, code_index: CodeIndex) -> dict: ...
```

**修改**: `python-agent/memory/redis_memory.py` 新增方法:
```python
def store_code_knowledge(self, project_key: str, knowledge: dict) -> None: ...
def get_code_knowledge(self, project_key: str) -> dict: ...
def store_file_summary(self, project_key: str, file_path: str, summary: str) -> None: ...
def get_file_summaries(self, project_key: str) -> dict[str, str]: ...
def store_error_pattern(self, project_key: str, error: str, fix: str) -> None: ...
def get_error_fixes(self, project_key: str, error: str) -> list[str]: ...
```

**实现要点**：
- Redis Hash 存储，key 格式 `{namespace}:{project_key}:knowledge`
- 任务成功后自动回写: 文件摘要 + 错误模式 + 架构笔记

**验证**: 第一个任务写入知识 → 第二个任务加载并使用知识上下文

---

#### Task 2.5: Validation Gate 扩展

**修改**: `python-agent/generators/validation_gate.py`

新增校验函数:
- `_validate_typescript_syntax()` — 大括号平衡、import/export 检查
- `_validate_react_component()` — JSX return、export default
- `_validate_redux_pattern()` — reducer 函数签名
- `_validate_npm_project()` — package.json 有效性

`validate()` 自动检测项目类型（检查 tsconfig.json、react 依赖）并应用对应校验器

---

#### Task 2.6: Fix Loop 扩展

**修改**: `python-agent/generators/fix_loop.py`

新增修复策略:
- `_fix_typescript_errors()` — TS 编译错误
- `_fix_import_errors()` — 模块路径错误（用 CodeIndex 查找正确路径）
- `_fix_redux_errors()` — Redux 相关错误

`_categorize_errors()` 识别 TS/React/Redux 错误模式并路由

---

### Week 3: 集成与演示（Day 15-21）

**目标**：端到端全流程验证、Android 适配、文档

#### Task 3.1: Conduit E2E 测试

**场景**: "给文章列表中的每篇文章加一个收藏数徽章"

**期望流程**:
```
RepoBootstrap → CodeIndex → DialogueManager(无需澄清) → IntentAgent(code_change)
→ PlannerAgent(方案) → [PLAN GATE] → CoderAgent(修改 2-3 个文件)
→ [CODE GATE] → ReviewerAgent → TestGenerator → TesterAgent → KnowledgeExtractor → TASK_DONE
```

**新建**: `python-agent/tests/test_conduit_e2e.py`, `python-agent/examples/conduit_task.json`

---

#### Task 3.2: 多领域覆盖

6 个场景覆盖 Conduit 全部领域:
1. Auth: "注册表单加邮箱格式校验"
2. Articles: "加文章阅读时间估算"
3. Comments: "给自己的评论加删除按钮"
4. Favorites: "个人页加收藏文章 Tab"
5. Profiles: "个人主页显示文章数量"
6. Tags: "首页加热门标签侧边栏"

至少 4/6 成功通过

---

#### Task 3.3: Android App 适配

**修改**: `mobile-app/.../AppUi.kt`
- 澄清对话框 (question + options + 文本输入)
- 方案审批页面 (plan steps + approve/reject + 反馈)
- 代码索引摘要卡片
- 测试生成进度指示器

**修改**: `mobile-app/.../Models.kt` — 新增 ClarificationRequest、PlanApprovalRequest 数据类

---

#### Task 3.4: Fix Loop + Knowledge 联动

**修改**: `fix_loop.py` — 修复前先查 `get_error_fixes()` 已知方案
**修改**: `agent_orchestrator.py` — 修复成功后 `store_error_pattern()`

---

#### Task 3.5: 文档与演示脚本

**新建**:
- `docs/super-individual-architecture.md`
- `docs/super-individual-demo-script.md`
- `python-agent/examples/conduit_demo.py`
- `python-agent/examples/conduit_tasks.json`

---

## 五、依赖关系

```
Week 1:
  GitTool(1.1) ──┐
  CodeIndex(1.2) ─┼── RepoBootstrap(1.4) ── Orchestrator(1.6)
  DialogueMgr(1.3)┘         │
  EventTypes(1.5) ──────────┘

Week 2:
  CoderAgent(2.1) ─── depends on CodeIndex(1.2)
  TestGenerator(2.2) ─ depends on CodeIndex(1.2) + LLMClient
  HumanGate(2.3) ───── depends on EventTypes(1.5)
  Knowledge(2.4) ───── depends on RedisMemory(existing)
  Validation(2.5) ──── independent
  FixLoop(2.6) ─────── depends on Knowledge(2.4) + Validation(2.5)

Week 3:
  E2E(3.1) ─── depends on all Week 1 + Week 2
  Android(3.3) ── depends on EventTypes(1.5) + HumanGate(2.3)
```

---

## 六、风险缓解

| 风险 | 缓解 |
|------|------|
| LLM 多文件编辑延迟 | `to_context_summary()` 上限 3000 tokens，`max_tokens: 4096` |
| Git 操作在 sandbox 失败 | `GitTool` 本地 fallback 模式 |
| TS 编译错误修复不了 | Fix loop 上限 3 轮，未解决的暴露到人工门控 |
| Conduit 仓库结构变化 | 固定 commit hash |
| 3 周时间紧张 | 每周产出可演示增量，MVP 优先 |

---

## 七、验证标准

**端到端成功标准**:
1. 系统能 clone Conduit 仓库并建立代码索引
2. 用户输入需求后，系统能定位相关文件并做增量修改
3. 自动生成测试并通过 `npm test`
4. 每个阶段可通过 Android App 审批
5. 知识在任务间持久化和复用
6. 至少 4 个 Conduit 领域场景成功跑通

---

## 八、关键文件路径

| 文件 | 角色 | 操作 |
|------|------|------|
| `python-agent/tools/git_tool.py` | Git 操作 | **新建** |
| `python-agent/tools/code_index.py` | 代码索引 | **新建** |
| `python-agent/tools/repo_bootstrap.py` | 仓库克隆+依赖安装 | **新建** |
| `python-agent/agents/dialogue_manager.py` | 多轮对话 | **新建** |
| `python-agent/generators/test_generator.py` | 测试生成 | **新建** |
| `python-agent/plugins/human_gate.py` | 全阶段人工门控 | **新建** |
| `python-agent/memory/knowledge_extractor.py` | 知识提取 | **新建** |
| `python-agent/agents/coder_agent.py` | 增量修改重构 | **修改** |
| `python-agent/agents/tester_agent.py` | 集成测试生成 | **修改** |
| `python-agent/orchestrator/agent_orchestrator.py` | 集成所有新组件 | **修改** |
| `python-agent/memory/redis_memory.py` | 知识存储扩展 | **修改** |
| `python-agent/generators/validation_gate.py` | TS/React/Express 校验 | **修改** |
| `python-agent/generators/fix_loop.py` | TS 错误修复策略 | **修改** |
| `shared-protocol/.../EventType.java` | 新增事件类型 | **修改** |
| `shared-protocol/.../payload/` | 新增 Payload 类 | **新建** (9 个) |
| `control-plane-spring/.../TaskService.java` | 新事件分类 | **修改** |
| `mobile-app/.../AppUi.kt` | 新事件 UI | **修改** |
| `python-agent/main.py` | 接线新组件 | **修改** |
