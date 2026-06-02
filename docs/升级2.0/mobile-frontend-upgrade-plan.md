# AutoCode 移动端前端交互体验升级方案

> 基于现有代码分析，针对用户反馈的15个核心问题，提出系统性升级方案。

---

## 一、问题诊断总览

### 1.1 问题分类矩阵

| 维度 | 问题数量 | 严重程度 | 影响范围 |
|------|----------|----------|----------|
| 信息架构 | 2 | 高 | 全局导航 |
| 表单设计 | 3 | 高 | 任务创建流程 |
| 反馈机制 | 3 | 中 | 全局交互 |
| 视觉设计 | 3 | 中 | 全局体验 |
| 性能优化 | 2 | 高 | 大数据场景 |
| 无障碍 | 2 | 低 | 特殊用户群 |

### 1.2 核心问题清单

| # | 问题 | 现状 | 影响 |
|---|------|------|------|
| 1 | 登录流程简陋 | 手动输入服务器地址，无验证、无历史、无引导 | 新用户不知道该填什么 |
| 2 | 首页毫无价值 | 只读文本堆砌，无操作入口 | 用户不知道下一步做什么 |
| 3 | 任务创建体验差 | 140dp文本框，无模板、无引导、无附件 | 用户难以描述复杂需求 |
| 4 | 语音输入形同虚设 | 直接调用系统识别，无反馈、无编辑 | 识别错误无法修正 |
| 5 | 任务详情信息过载 | 事件流堆砌，无筛选、无搜索、无分类 | 用户找不到关键信息 |
| 6 | 审批交互设计失败 | 只有批准/拒绝按钮，无风险说明 | 用户缺乏决策依据 |
| 7 | 产物预览体验差 | 纯文本显示，无高亮、无渲染 | 无法有效查看代码 |
| 8 | 网络状态反馈缺失 | 只有一个进度条 | 用户不知道发生了什么 |
| 9 | 导航结构混乱 | 5个Tab功能重叠 | 用户迷失方向 |
| 10 | 错误处理敷衍 | 红色文本提示 | 用户不知道如何恢复 |
| 11 | 无障碍支持缺失 | 无内容描述、无屏幕阅读器支持 | 无法服务特殊用户 |
| 12 | 性能优化缺失 | 每次重组重新排序、无分页 | 大数据量卡顿 |
| 13 | 国际化缺失 | 硬编码中文字符串 | 无法国际化 |
| 14 | 空状态设计缺失 | 纯文本提示 | 用户不知道下一步 |
| 15 | 深色模式缺失 | 无深色模式支持 | 夜间使用刺眼 |

---

## 二、信息架构重构

### 2.1 现状问题

```
当前导航结构（5个Tab）：
┌─────┬─────┬─────┬─────┬─────┐
│ 首页 │ 任务 │ 项目 │ 产物 │ 我的 │
└─────┴─────┴─────┴─────┴─────┘

问题：
- "首页"和"任务"功能重叠
- "产物"和"任务"强关联却分开
- "项目"只有选择功能，不值得单独Tab
- "我的"里面只有登出和设置
```

### 2.2 新导航结构

```
新导航结构（4个Tab）：
┌───────────┬───────────┬───────────┬───────────┐
│   工作    │   历史    │   产物    │   设置    │
│  (Work)   │ (History) │(Artifacts)│ (Settings)│
├───────────┼───────────┼───────────┼───────────┤
│ 快捷入口  │ 任务列表  │ 产物浏览  │ 连接配置  │
│ 最近任务  │ 筛选搜索  │ 版本历史  │ 深色模式  │
│ 使用统计  │ 详情查看  │ 在线预览  │ 语言切换  │
│ 推荐模板  │ 审批处理  │ 发布管理  │ 账户管理  │
└───────────┴───────────┴───────────┴───────────┘

变更说明：
1. 合并"首页"到"工作"Tab，增加快捷操作入口
2. "任务"改名为"历史"，强调任务记录
3. "项目"降级为设置页内的选择器
4. "我的"改名为"设置"，更符合用户心智
```

### 2.3 实现代码

```kotlin
// 新的Tab定义
private sealed class Tab(
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    data object Work : Tab("work", "工作", Icons.Filled.Work)
    data object History : Tab("history", "历史", Icons.Filled.History)
    data object Artifacts : Tab("artifacts", "产物", Icons.Filled.Folder)
    data object Settings : Tab("settings", "设置", Icons.Filled.Settings)
}
```

---

## 三、登录流程升级

### 3.1 现状问题

```kotlin
// 当前实现：三个空白输入框
OutlinedTextField(
    value = baseUrlDraft,
    onValueChange = { baseUrlDraft = it },
    label = { Text("控制面地址") },
    placeholder = { Text("例如：http://10.92.85.245:8058") },
)
```

问题：
- 没有服务器地址验证
- 没有连接测试按钮
- 没有历史地址记忆
- 没有扫码配置
- 没有企业部署预设

### 3.2 升级方案

#### 3.2.1 数据模型

```kotlin
// 登录配置
data class LoginConfig(
    val presetServers: List<PresetServer>,      // 企业预设服务器
    val recentServers: List<RecentServer>,      // 历史连接
    val allowManualInput: Boolean = true,       // 是否允许手动输入
    val qrCodeEnabled: Boolean = true,          // 扫码配置
)

// 预设服务器
data class PresetServer(
    val id: String,
    val name: String,           // "公司测试环境"
    val baseUrl: String,
    val icon: String? = null,
    val requiresVpn: Boolean = false,
)

// 历史连接
data class RecentServer(
    val baseUrl: String,
    val lastUsed: Long,
    val displayName: String?,
    val connectionStatus: ConnectionStatus,
)

enum class ConnectionStatus {
    REACHABLE, UNREACHABLE, UNKNOWN
}

// 连接测试结果
data class ConnectionTestResult(
    val success: Boolean,
    val latencyMs: Long?,
    val serverVersion: String?,
    val errorMessage: String?,
)
```

#### 3.2.2 新登录界面

```kotlin
@Composable
fun EnhancedLoginScreen(
    config: LoginConfig,
    onServerSelect: (PresetServer) -> Unit,
    onManualInput: (String) -> Unit,
    onQrCodeScan: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        // 标题
        Column {
            Text("AutoCode", style = MaterialTheme.typography.headlineLarge)
            Text("AI 驱动的代码生成平台", style = MaterialTheme.typography.bodyMedium)
        }
        
        // 1. 企业预设服务器卡片
        if (config.presetServers.isNotEmpty()) {
            Column {
                Text("快速连接", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(config.presetServers) { server ->
                        PresetServerCard(
                            server = server,
                            onClick = { onServerSelect(server) }
                        )
                    }
                }
            }
        }
        
        // 2. 历史连接（带状态指示）
        if (config.recentServers.isNotEmpty()) {
            Column {
                Text("最近连接", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                config.recentServers.forEach { server ->
                    RecentServerItem(
                        server = server,
                        onClick = { onManualInput(server.baseUrl) }
                    )
                    Spacer(Modifier.height(8.dp))
                }
            }
        }
        
        // 3. 扫码配置入口
        if (config.qrCodeEnabled) {
            OutlinedButton(
                onClick = onQrCodeScan,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Filled.QrCodeScanner, null)
                Spacer(Modifier.width(8.dp))
                Text("扫码配置")
            }
        }
        
        // 4. 手动输入（折叠式）
        if (config.allowManualInput) {
            var expanded by remember { mutableStateOf(false) }
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "收起手动输入" else "手动输入服务器地址")
            }
            AnimatedVisibility(expanded) {
                ManualServerInput(
                    onConnect = onManualInput,
                    onTestConnection = { url -> testConnection(url) }
                )
            }
        }
    }
}

@Composable
fun ManualServerInput(
    onConnect: (String) -> Unit,
    onTestConnection: (String) -> ConnectionTestResult,
) {
    var url by remember { mutableStateOf("") }
    var testResult by remember { mutableStateOf<ConnectionTestResult?>(null) }
    var testing by remember { mutableStateOf(false) }
    
    Column {
        OutlinedTextField(
            value = url,
            onValueChange = { 
                url = it
                testResult = null
            },
            label = { Text("服务器地址") },
            placeholder = { Text("https://autocode.example.com") },
            trailingIcon = {
                if (testing) {
                    CircularProgressIndicator(Modifier.size(20.dp))
                } else {
                    IconButton(onClick = {
                        testing = true
                        testResult = onTestConnection(url)
                        testing = false
                    }) {
                        Icon(Icons.Filled.WifiFind, "测试连接")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth()
        )
        
        // 连接测试结果
        testResult?.let { result ->
            Spacer(Modifier.height(8.dp))
            ConnectionTestResultChip(result)
        }
        
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { onConnect(url) },
            enabled = url.isNotBlank() && testResult?.success == true,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("连接")
        }
    }
}

@Composable
fun ConnectionTestResultChip(result: ConnectionTestResult) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        if (result.success) {
            Icon(
                Icons.Filled.CheckCircle,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary
            )
            Text("连接成功", color = MaterialTheme.colorScheme.primary)
            result.latencyMs?.let { Text("${it}ms", style = MaterialTheme.typography.bodySmall) }
            result.serverVersion?.let { Text("v$it", style = MaterialTheme.typography.bodySmall) }
        } else {
            Icon(
                Icons.Filled.Error,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.error
            )
            Text(result.errorMessage ?: "连接失败", color = MaterialTheme.colorScheme.error)
        }
    }
}
```

---

## 四、首页升级为工作台

### 4.1 现状问题

```kotlin
// 当前实现：只读文本堆砌
@Composable
private fun HomeTab(vm: AppViewModel) {
    Column(Modifier.padding(20.dp)) {
        Text("首页", style = MaterialTheme.typography.headlineSmall)
        Text("已登录：${state.session?.displayName ?: "—"}")
        Text("当前项目：${project?.name ?: state.selectedProjectId ?: "未选择"}")
        Text("生成目标：${state.generationTarget.displayLabel()}")
        Text("代理身份：${state.agentProfile.displayLabel()}")
        // ...
    }
}
```

问题：
- 没有快捷操作入口
- 没有最近任务卡片
- 没有使用统计
- 没有推荐模板
- 没有任何可交互元素

### 4.2 升级方案

```kotlin
@Composable
fun WorkTab(vm: AppViewModel, nav: NavHostController) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 1. 欢迎卡片 + 快速创建
        item {
            QuickCreateCard(
                userName = state.session?.displayName,
                onCreateTask = { nav.navigate("task/create") },
                onVoiceInput = { /* 语音创建 */ }
            )
        }
        
        // 2. 使用统计
        item {
            UsageStatsCard(
                totalTasks = state.tasks.size,
                succeededTasks = state.tasks.count { it.status == TaskStatus.SUCCEEDED },
                thisWeekTasks = state.tasks.count { 
                    it.createdAt > System.currentTimeMillis() - 7 * 24 * 60 * 60 * 1000 
                }
            )
        }
        
        // 3. 最近任务
        item {
            Text("最近任务", style = MaterialTheme.typography.titleMedium)
        }
        items(state.tasks.sortedByDescending { it.updatedAt }.take(5)) { task ->
            RecentTaskCard(
                task = task,
                onClick = { nav.navigate("task/${task.id}") }
            )
        }
        
        // 4. 推荐模板
        item {
            Text("推荐模板", style = MaterialTheme.typography.titleMedium)
        }
        item {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                items(getRecommendedTemplates()) { template ->
                    TemplateCard(
                        template = template,
                        onClick = { nav.navigate("task/create?template=${template.id}") }
                    )
                }
            }
        }
        
        // 5. 待处理审批
        if (state.pendingApprovals.isNotEmpty()) {
            item {
                PendingApprovalsBanner(
                    count = state.pendingApprovals.size,
                    onClick = { nav.navigate("approvals") }
                )
            }
        }
    }
}

@Composable
fun QuickCreateCard(
    userName: String?,
    onCreateTask: () -> Unit,
    onVoiceInput: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(Modifier.padding(20.dp)) {
            Text(
                "你好，${userName ?: "用户"}",
                style = MaterialTheme.typography.headlineSmall
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "描述你的需求，AI 帮你生成代码",
                style = MaterialTheme.typography.bodyMedium
            )
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onCreateTask) {
                    Icon(Icons.Filled.Add, null)
                    Spacer(Modifier.width(8.dp))
                    Text("创建任务")
                }
                OutlinedButton(onClick = onVoiceInput) {
                    Icon(Icons.Filled.Mic, null)
                    Spacer(Modifier.width(8.dp))
                    Text("语音描述")
                }
            }
        }
    }
}

@Composable
fun UsageStatsCard(
    totalTasks: Int,
    succeededTasks: Int,
    thisWeekTasks: Int,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            StatItem(label = "总任务", value = totalTasks.toString())
            StatItem(label = "已完成", value = succeededTasks.toString())
            StatItem(label = "本周", value = thisWeekTasks.toString())
        }
    }
}

@Composable
fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = MaterialTheme.typography.headlineMedium)
        Text(label, style = MaterialTheme.typography.bodySmall)
    }
}

// 模板数据
data class TaskTemplate(
    val id: String,
    val name: String,
    val description: String,
    val promptTemplate: String,
    val icon: ImageVector,
    val category: String,
)

fun getRecommendedTemplates(): List<TaskTemplate> = listOf(
    TaskTemplate(
        id = "web_dashboard",
        name = "数据仪表盘",
        description = "可视化数据展示页面",
        promptTemplate = "创建一个数据仪表盘，包含图表和数据表格",
        icon = Icons.Filled.Dashboard,
        category = "Web"
    ),
    TaskTemplate(
        id = "crud_admin",
        name = "管理后台",
        description = "增删改查管理界面",
        promptTemplate = "创建一个管理后台，支持数据的增删改查操作",
        icon = Icons.Filled.AdminPanelSettings,
        category = "Web"
    ),
    TaskTemplate(
        id = "landing_page",
        name = "落地页",
        description = "产品展示落地页",
        promptTemplate = "创建一个产品落地页，包含产品介绍和联系表单",
        icon = Icons.Filled.Web,
        category = "Web"
    ),
)
```

---

## 五、任务创建升级

### 5.1 现状问题

```kotlin
// 当前实现：一个140dp文本框
OutlinedTextField(
    value = prompt,
    onValueChange = { prompt = it },
    label = { Text("自然语言描述") },
    modifier = Modifier.weight(1f).height(140.dp),
    minLines = 4,
)
```

问题：
- 没有需求模板
- 没有示例提示
- 没有语音转文字的实时反馈
- 没有附件上传
- 没有历史需求复用

### 5.2 升级方案

```kotlin
@Composable
fun TaskCreationScreen(
    vm: AppViewModel,
    templateId: String?,
    onCreated: (String) -> Unit,
    onBack: () -> Unit,
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var prompt by remember { mutableStateOf("") }
    var attachments by remember { mutableStateOf<List<Attachment>>(emptyList()) }
    var selectedTemplate by remember { mutableStateOf<TaskTemplate?>(null) }
    var expandedGuidance by remember { mutableStateOf(true) }
    
    // 加载模板
    LaunchedEffect(templateId) {
        templateId?.let { id ->
            selectedTemplate = getRecommendedTemplates().find { it.id == id }
            selectedTemplate?.let { prompt = it.promptTemplate }
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("创建任务") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 1. 模板选择
            TemplateSelector(
                selectedTemplate = selectedTemplate,
                onTemplateSelect = { template ->
                    selectedTemplate = template
                    prompt = template.promptTemplate
                }
            )
            
            // 2. 需求描述引导
            if (expandedGuidance) {
                GuidanceCard(onDismiss = { expandedGuidance = false })
            }
            
            // 3. 需求输入区
            EnhancedPromptInput(
                prompt = prompt,
                onPromptChange = { prompt = it },
                attachments = attachments,
                onAttachmentsChange = { attachments = it },
                onVoiceInput = { /* 语音输入 */ }
            )
            
            // 4. 高级选项
            AdvancedOptionsSection(
                generationTarget = state.generationTarget,
                agentProfile = state.agentProfile,
                onTargetChange = { /* ... */ },
                onProfileChange = { /* ... */ }
            )
            
            // 5. 提交按钮
            Button(
                onClick = {
                    vm.createTaskWithAttachments(prompt, attachments, selectedTemplate?.id)
                },
                enabled = prompt.isNotBlank(),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("创建任务")
            }
        }
    }
}

@Composable
fun GuidanceCard(onDismiss: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("如何描述需求？", style = MaterialTheme.typography.titleSmall)
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Filled.Close, "关闭")
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                """
                好的需求描述包含：
                • 功能目标：想要实现什么功能
                • 技术要求：使用什么技术栈（可选）
                • 样式偏好：UI风格要求（可选）
                • 参考示例：类似产品的链接（可选）
                
                示例：
                "创建一个待办事项应用，支持添加、删除、标记完成功能，
                使用简洁的 Material Design 风格，数据保存在本地存储"
                """.trimIndent(),
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

@Composable
fun EnhancedPromptInput(
    prompt: String,
    onPromptChange: (String) -> Unit,
    attachments: List<Attachment>,
    onAttachmentsChange: (List<Attachment>) -> Unit,
    onVoiceInput: () -> Unit,
) {
    Column {
        Text("需求描述", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        
        OutlinedTextField(
            value = prompt,
            onValueChange = onPromptChange,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 120.dp, max = 300.dp),
            placeholder = { 
                Text("描述你想要创建的应用或功能...\n\n例如：创建一个用户管理页面，支持搜索、添加、编辑用户") 
            },
            trailingIcon = {
                Text(
                    "${prompt.length}/2000",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(end = 8.dp)
                )
            }
        )
        
        Spacer(Modifier.height(8.dp))
        
        // 附件和语音按钮
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            AttachmentButton(
                attachments = attachments,
                onAttachmentsChange = onAttachmentsChange
            )
            VoiceInputButton(onVoiceInput = onVoiceInput)
        }
        
        // 附件列表
        if (attachments.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            AttachmentList(
                attachments = attachments,
                onRemove = { onAttachmentsChange(attachments - it) }
            )
        }
    }
}

// 附件数据类
data class Attachment(
    val id: String,
    val name: String,
    val mimeType: String,
    val size: Long,
    val uri: Uri,
)
```

---

## 六、语音输入升级

### 6.1 现状问题

```kotlin
// 当前实现：直接调用系统语音识别
private fun buildSpeechRecognizerIntent(): Intent =
    Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
    }
```

问题：
- 没有语音反馈（"正在听..."）
- 没有识别结果预览
- 没有编辑识别结果的机会
- 没有连续语音输入
- 没有方言支持

### 6.2 升级方案

```kotlin
@Composable
fun EnhancedVoiceInputButton(
    onResult: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    var isListening by remember { mutableStateOf(false) }
    var recognizedText by remember { mutableStateOf("") }
    var showEditDialog by remember { mutableStateOf(false) }
    
    val speechRecognizer = remember {
        SpeechRecognizer.createSpeechRecognizer(context)
    }
    
    val recognitionListener = remember {
        object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                isListening = true
            }
            
            override fun onRmsChanged(rmsdB: Float) {
                // 音量变化，可用于可视化
            }
            
            override fun onEndOfSpeech() {
                isListening = false
            }
            
            override fun onError(error: Int) {
                isListening = false
                // 显示错误提示
            }
            
            override fun onResults(results: Bundle?) {
                isListening = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) {
                    recognizedText = matches[0]
                    showEditDialog = true
                }
            }
            
            override fun onPartialResults(partialResults: Bundle?) {
                // 实时部分结果
                val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) {
                    recognizedText = matches[0]
                }
            }
            
            override fun onBeginningOfSpeech() {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        }
    }
    
    DisposableEffect(speechRecognizer) {
        speechRecognizer.setRecognitionListener(recognitionListener)
        onDispose { speechRecognizer.destroy() }
    }
    
    Box(modifier = modifier) {
        FilledTonalButton(
            onClick = {
                if (isListening) {
                    speechRecognizer.stopListening()
                } else {
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "请描述你的需求")
                    }
                    speechRecognizer.startListening(intent)
                }
            }
        ) {
            if (isListening) {
                PulsatingMicIcon()
                Spacer(Modifier.width(8.dp))
                Text("正在听...")
            } else {
                Icon(Icons.Filled.Mic, null)
                Spacer(Modifier.width(8.dp))
                Text("语音描述")
            }
        }
        
        // 实时识别结果显示
        if (isListening && recognizedText.isNotEmpty()) {
            Card(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(bottom = 60.dp)
            ) {
                Text(
                    recognizedText,
                    modifier = Modifier.padding(12.dp),
                    maxLines = 3
                )
            }
        }
    }
    
    // 编辑对话框
    if (showEditDialog) {
        VoiceResultEditDialog(
            text = recognizedText,
            onConfirm = {
                onResult(it)
                showEditDialog = false
                recognizedText = ""
            },
            onDismiss = {
                showEditDialog = false
                recognizedText = ""
            },
            onRetry = { showEditDialog = false }
        )
    }
}

@Composable
fun PulsatingMicIcon() {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(500),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )
    
    Icon(
        Icons.Filled.Mic,
        contentDescription = null,
        modifier = Modifier.scale(scale),
        tint = MaterialTheme.colorScheme.primary
    )
}

@Composable
fun VoiceResultEditDialog(
    text: String,
    onConfirm: (String) -> Unit,
    onDismiss: () -> Unit,
    onRetry: () -> Unit,
) {
    var editedText by remember(text) { mutableStateOf(text) }
    
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("识别结果") },
        text = {
            Column {
                Text("请检查并编辑识别结果：", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = editedText,
                    onValueChange = { editedText = it },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 100.dp),
                    minLines = 3
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(editedText) }) {
                Text("确认")
            }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onRetry) { Text("重试") }
                TextButton(onClick = onDismiss) { Text("取消") }
            }
        }
    )
}
```

---

## 七、任务详情页升级

### 7.1 现状问题

```kotlin
// 当前实现：事件流堆砌
LazyColumn {
    items(events, key = { eventStableKey(it) }) { event ->
        AgentEventItem(event = event, fallbackLine = vm.eventLine(event))
    }
}
```

问题：
- 没有事件分类筛选
- 没有事件搜索
- 没有事件折叠
- 没有时间线可视化
- 没有错误高亮

### 7.2 升级方案

```kotlin
@Composable
fun EnhancedTaskDetailScreen(
    vm: AppViewModel,
    taskId: String,
    onBack: () -> Unit,
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val task = state.tasks.find { it.id == taskId }
    val allEvents = state.taskEvents[taskId].orEmpty()
    
    // 筛选状态
    var selectedEventType by remember { mutableStateOf<Set<String>>(emptySet()) }
    var searchQuery by remember { mutableStateOf("") }
    var showOnlyErrors by remember { mutableStateOf(false) }
    
    // 筛选后的事件
    val filteredEvents = remember(allEvents, selectedEventType, searchQuery, showOnlyErrors) {
        allEvents
            .filter { event ->
                if (selectedEventType.isEmpty()) true
                else event.type in selectedEventType
            }
            .filter { event ->
                if (searchQuery.isBlank()) true
                else event.toString().contains(searchQuery, ignoreCase = true)
            }
            .filter { event ->
                if (!showOnlyErrors) true
                else event.type in listOf("TASK_FAILED", "TOOL_END") && 
                     event.payload.toString().contains("error", ignoreCase = true)
            }
    }
    
    // 事件类型统计
    val eventTypeCounts = remember(allEvents) {
        allEvents.groupingBy { it.type ?: "unknown" }.eachCount()
    }
    
    Scaffold(
        topBar = {
            TaskDetailTopBar(
                task = task,
                onBack = onBack,
                onSearch = { searchQuery = it },
                onFilter = { showOnlyErrors = it }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            // 任务概览卡片
            task?.let { TaskOverviewCard(task = it) }
            
            // 事件类型筛选器
            EventTypeFilterChips(
                counts = eventTypeCounts,
                selected = selectedEventType,
                onSelectionChange = { selectedEventType = it }
            )
            
            // 事件列表（分页）
            PaginatedEventList(
                events = filteredEvents,
                onLoadMore = { /* 加载更多 */ },
                eventLineProvider = { vm.eventLine(it) }
            )
        }
    }
}

@Composable
fun EventTypeFilterChips(
    counts: Map<String, Int>,
    selected: Set<String>,
    onSelectionChange: (Set<String>) -> Unit,
) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            FilterChip(
                selected = selected.isEmpty(),
                onClick = { onSelectionChange(emptySet()) },
                label = { Text("全部 (${counts.values.sum()})") }
            )
        }
        
        items(counts.entries.toList()) { (type, count) ->
            FilterChip(
                selected = type in selected,
                onClick = {
                    onSelectionChange(
                        if (type in selected) selected - type
                        else selected + type
                    )
                },
                label = { Text("${eventTypeLabel(type)} ($count)") }
            )
        }
    }
}

@Composable
fun PaginatedEventList(
    events: List<TaskEventDto>,
    onLoadMore: () -> Unit,
    eventLineProvider: (TaskEventDto) -> String,
) {
    val listState = rememberLazyListState()
    
    // 检测滚动到底部
    LaunchedEffect(listState) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index }
            .collect { lastVisibleIndex ->
                if (lastVisibleIndex != null && lastVisibleIndex >= events.size - 10) {
                    onLoadMore()
                }
            }
    }
    
    LazyColumn(
        state = listState,
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(events, key = { eventStableKey(it) }) { event ->
            AgentEventItem(event = event, fallbackLine = eventLineProvider(event))
        }
    }
}

@Composable
fun TaskOverviewCard(task: TaskItem) {
    Card(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(task.prompt, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                StatusChip(status = task.status)
                Text("${task.progress}%", style = MaterialTheme.typography.bodySmall)
                Text(formatRelativeTime(task.updatedAt), style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(12.dp))
            LinearProgressIndicator(
                progress = { task.progress / 100f },
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}
```

---

## 八、审批交互升级

### 8.1 现状问题

```kotlin
// 当前实现：只有批准/拒绝按钮
Row {
    Button(onClick = { onApprove(comment) }) { Text("批准") }
    Button(onClick = { onReject(comment) }) { Text("拒绝") }
}
```

问题：
- 没有风险说明
- 没有命令详情展示
- 没有历史审批参考
- 没有审批超时倒计时可视化
- 没有部分批准选项

### 8.2 升级方案

```kotlin
@Composable
fun EnhancedApprovalBottomSheet(
    approval: ApprovalRequest,
    historicalApprovals: List<ApprovalHistoryItem>,
    onApprove: (comment: String?) -> Unit,
    onReject: (comment: String?) -> Unit,
    onTimeout: () -> Unit,
    onDismiss: () -> Unit,
) {
    var comment by remember { mutableStateOf("") }
    var handling by remember { mutableStateOf(false) }
    var secondsLeft by remember { mutableStateOf(approval.timeoutSeconds) }
    var showHistory by remember { mutableStateOf(false) }
    var expandedRiskInfo by remember { mutableStateOf(false) }
    
    // 倒计时
    LaunchedEffect(approval.approvalId) {
        while (secondsLeft > 0 && !handling) {
            delay(1000)
            secondsLeft--
        }
        if (secondsLeft <= 0 && !handling) {
            handling = true
            onTimeout()
        }
    }
    
    ModalBottomSheet(onDismissRequest = { if (!handling) onDismiss() }) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // 标题和倒计时
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("审批请求", style = MaterialTheme.typography.titleLarge)
                CountdownChip(secondsLeft = secondsLeft, total = approval.timeoutSeconds)
            }
            
            Spacer(Modifier.height(16.dp))
            
            // 风险等级卡片
{}
            RiskLevelCard(
                riskScore = approval.riskScore,
                expanded = expandedRiskInfo,
                onExpand = { expandedRiskInfo = !expandedRiskInfo }
            )
            
            Spacer(Modifier.height(16.dp))
            
            // 命令详情
            CommandDetailCard(
                action = approval.action,
                tool = approval.tool,
                command = approval.command,
                cwd = approval.cwd,
                reason = approval.reason
            )
            
            // 历史审批参考
            if (historicalApprovals.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                HistoricalApprovalsSection(
                    approvals = historicalApprovals.take(3),
                    expanded = showHistory,
                    onToggle = { showHistory = !showHistory }
                )
            }
            
            // 审批备注
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = comment,
                onValueChange = { comment = it },
                label = { Text("审批备注（可选）") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2
            )
            
            // 操作按钮
            Spacer(Modifier.height(16.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        if (!handling) {
                            handling = true
                            onReject(comment.takeIf { it.isNotBlank() })
                        }
                    },
                    enabled = !handling,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Icon(Icons.Filled.Close, null)
                    Spacer(Modifier.width(8.dp))
                    Text("拒绝")
                }
                
                Button(
                    onClick = {
                        if (!handling) {
                            handling = true
                            onApprove(comment.takeIf { it.isNotBlank() })
                        }
                    },
                    enabled = !handling,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Filled.Check, null)
                    Spacer(Modifier.width(8.dp))
                    Text("批准")
                }
            }
            
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
fun RiskLevelCard(
    riskScore: Double?,
    expanded: Boolean,
    onExpand: () -> Unit,
) {
    val riskLevel = remember(riskScore) {
        when {
            riskScore == null -> RiskLevel.UNKNOWN
            riskScore < 0.3 -> RiskLevel.LOW
            riskScore < 0.7 -> RiskLevel.MEDIUM
            else -> RiskLevel.HIGH
        }
    }
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = riskLevel.color.copy(alpha = 0.1f)
        )
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        riskLevel.icon,
                        contentDescription = null,
                        tint = riskLevel.color
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "风险等级：${riskLevel.label}",
                        style = MaterialTheme.typography.titleSmall,
                        color = riskLevel.color
                    )
                }
                
                riskScore?.let {
                    Text(
                        String.format("%.2f", it),
                        style = MaterialTheme.typography.labelLarge,
                        color = riskLevel.color
                    )
                }
            }
            
            AnimatedVisibility(expanded) {
                Column {
                    Spacer(Modifier.height(12.dp))
                    Text(
                        riskLevel.description,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onExpand) {
                Text(if (expanded) "收起详情" else "查看详情")
            }
        }
    }
}

enum class RiskLevel(
    val label: String,
    val color: Color,
    val icon: ImageVector,
    val description: String,
) {
    LOW(
        label = "低风险",
        color = Color(0xFF4CAF50),
        icon = Icons.Filled.CheckCircle,
        description = "该命令风险较低，通常是安全的读取操作。"
    ),
    MEDIUM(
        label = "中风险",
        color = Color(0xFFFF9800),
        icon = Icons.Filled.Warning,
        description = "该命令有一定风险，可能修改文件或执行受限操作。建议仔细审查命令内容。"
    ),
    HIGH(
        label = "高风险",
        color = Color(0xFFF44336),
        icon = Icons.Filled.Dangerous,
        description = "该命令风险较高，可能删除文件、执行系统命令或访问敏感数据。请谨慎审批。"
    ),
    UNKNOWN(
        label = "未知风险",
        color = Color.Gray,
        icon = Icons.Filled.Help,
        description = "无法评估该命令的风险等级。"
    );
}

@Composable
fun CountdownChip(secondsLeft: Int, total: Int) {
    val progress = secondsLeft.toFloat() / total.toFloat()
    val color = when {
        secondsLeft > total * 0.5 -> MaterialTheme.colorScheme.primary
        secondsLeft > total * 0.2 -> Color(0xFFFF9800)
        else -> MaterialTheme.colorScheme.error
    }
    
    Surface(
        shape = MaterialTheme.shapes.small,
        color = color.copy(alpha = 0.1f)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Filled.Timer,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(16.dp)
            )
            Spacer(Modifier.width(4.dp))
            Text(
                "${secondsLeft}s",
                style = MaterialTheme.typography.labelMedium,
                color = color
            )
        }
    }
}

@Composable
fun CommandDetailCard(
    action: String?,
    tool: String?,
    command: String?,
    cwd: String?,
    reason: String?,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text("命令详情", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(12.dp))
            
            action?.let {
                DetailRow(label = "动作", value = it)
            }
            
            tool?.let {
                DetailRow(label = "工具", value = it)
            }
            
            command?.let {
                Spacer(Modifier.height(8.dp))
                Text("命令：", style = MaterialTheme.typography.labelMedium)
                Spacer(Modifier.height(4.dp))
                CodeBlock(code = it)
            }
            
            cwd?.let {
                DetailRow(label = "工作目录", value = it, monospace = true)
            }
            
            reason?.let {
                Spacer(Modifier.height(8.dp))
                Text("原因：$it", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun CodeBlock(code: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Text(
            code,
            modifier = Modifier.padding(12.dp),
            fontFamily = FontFamily.Monospace,
            style = MaterialTheme.typography.bodySmall
        )
    }
}

@Composable
fun DetailRow(label: String, value: String, monospace: Boolean = false) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.labelMedium)
        Text(
            value,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = if (monospace) FontFamily.Monospace else FontFamily.Default,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false)
        )
    }
}

// 历史审批数据类
data class ApprovalHistoryItem(
    val approvalId: String,
    val command: String,
    val decision: String,
    val comment: String?,
    val timestamp: Long,
    val userName: String?,
)
```

---

## 九、产物预览升级

### 9.1 现状问题

```kotlin
// 当前实现：纯文本显示
data class ArtifactPreview(
    val title: String,
    val contentType: String?,
    val content: String,
    val truncated: Boolean,
    val byteSize: Int,
)
```

问题：
- 没有代码高亮
- 没有图片预览
- 没有HTML渲染
- 没有文件树结构
- 没有对比视图

### 9.2 升级方案

```kotlin
@Composable
fun EnhancedArtifactPreview(
    preview: ArtifactPreview,
    modifier: Modifier = Modifier,
) {
    when {
        // 图片预览
        preview.contentType?.startsWith("image/") == true -> {
            ImagePreview(preview = preview, modifier = modifier)
        }
        
        // HTML渲染
        preview.contentType == "text/html" -> {
            HtmlPreview(preview = preview, modifier = modifier)
        }
        
        // 代码高亮
        isCodeContentType(preview.contentType) -> {
            CodePreview(preview = preview, modifier = modifier)
        }
        
        // Markdown渲染
        preview.contentType == "text/markdown" -> {
            MarkdownPreview(preview = preview, modifier = modifier)
        }
        
        // JSON格式化
        preview.contentType?.contains("json") == true -> {
            JsonPreview(preview = preview, modifier = modifier)
        }
        
        // 默认文本
        else -> {
            TextPreview(preview = preview, modifier = modifier)
        }
    }
}

@Composable
fun CodePreview(preview: ArtifactPreview, modifier: Modifier = Modifier) {
    var lineNumbers by remember { mutableStateOf(true) }
    var wrapLines by remember { mutableStateOf(false) }
    
    Column(modifier = modifier) {
        // 工具栏
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(preview.title, style = MaterialTheme.typography.titleSmall)
            Row {
                // 行号开关
                IconButton(onClick = { lineNumbers = !lineNumbers }) {
                    Icon(
                        if (lineNumbers) Icons.Filled.FormatListNumbered 
                        else Icons.Outlined.FormatListNumbered,
                        "行号"
                    )
                }
                // 换行开关
                IconButton(onClick = { wrapLines = !wrapLines }) {
                    Icon(
                        if (wrapLines) Icons.Filled.WrapText 
                        else Icons.Outlined.WrapText,
                        "换行"
                    )
                }
                // 复制按钮
                IconButton(onClick = { /* 复制到剪贴板 */ }) {
                    Icon(Icons.Filled.ContentCopy, "复制")
                }
            }
        }
        
        Spacer(Modifier.height(8.dp))
        
        // 代码块
        val language = detectLanguage(preview.contentType, preview.title)
        val highlightedCode = remember(preview.content, language) {
            highlightCode(preview.content, language)
        }
        
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 400.dp),
            shape = MaterialTheme.shapes.small,
            color = MaterialTheme.colorScheme.surfaceVariant
        ) {
            LazyColumn(
                modifier = Modifier.padding(12.dp)
            ) {
                item {
                    AndroidView(
                        factory = { context ->
                            TextView(context).apply {
                                setTextIsSelectable(true)
                                typeface = Typeface.MONOSPACE
                                textSize = 12f
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                    useStdOut = true
                                }
                            }
                        },
                        update = { textView ->
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                                textView.text = Html.fromHtml(
                                    highlightedCode,
                                    Html.FROM_HTML_MODE_COMPACT
                                )
                            } else {
                                textView.text = Html.fromHtml(highlightedCode)
                            }
                        }
                    )
                }
            }
        }
        
        if (preview.truncated) {
            Spacer(Modifier.height(8.dp))
            Text(
                "预览已截断，完整内容共 ${preview.byteSize} 字节",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
fun ImagePreview(preview: ArtifactPreview, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(preview.title, style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(8.dp))
        
        // 使用 Coil 加载图片
        AsyncImage(
            model = preview.content, // Base64 或 URL
            contentDescription = preview.title,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 300.dp),
            contentScale = ContentScale.Fit
        )
    }
}

@Composable
fun HtmlPreview(preview: ArtifactPreview, modifier: Modifier = Modifier) {
    var showSource by remember { mutableStateOf(false) }
    
    Column(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(preview.title, style = MaterialTheme.typography.titleSmall)
            Row {
                FilterChip(
                    selected = !showSource,
                    onClick = { showSource = false },
                    label = { Text("渲染") }
                )
                Spacer(Modifier.width(8.dp))
                FilterChip(
                    selected = showSource,
                    onClick = { showSource = true },
                    label = { Text("源码") }
                )
            }
        }
        
        Spacer(Modifier.height(8.dp))
        
        if (showSource) {
            CodePreview(preview.copy(contentType = "text/html"))
        } else {
            AndroidView(
                factory = { context ->
                    WebView(context).apply {
                        settings.javaScriptEnabled = true
                        settings.loadWithOverviewMode = true
                        settings.useWideViewPort = true
                    }
                },
                update = { webView ->
                    webView.loadDataWithBaseURL(
                        null,
                        preview.content,
                        "text/html",
                        "UTF-8",
                        null
                    )
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 200.dp, max = 400.dp)
            )
        }
    }
}

@Composable
fun JsonPreview(preview: ArtifactPreview, modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(false) }
    val formattedJson = remember(preview.content) {
        runCatching {
            val jsonElement = Json.parseToJsonElement(preview.content)
            Json { prettyPrint = true }.encodeToString(JsonElement.serializer(), jsonElement)
        }.getOrElse { preview.content }
    }
    
    Column(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(preview.title, style = MaterialTheme.typography.titleSmall)
            IconButton(onClick = { expanded = !expanded }) {
                Icon(
                    if (expanded) Icons.Filled.UnfoldLess 
                    else Icons.Filled.UnfoldMore,
                    "展开/折叠"
                )
            }
        }
        
        Spacer(Modifier.height(8.dp))
        
        JsonTreeView(
            json = formattedJson,
            expanded = expanded,
            modifier = Modifier.fillMaxWidth()
        )
    }
}

fun isCodeContentType(contentType: String?): Boolean {
    if (contentType == null) return false
    val codeTypes = listOf(
        "text/javascript", "application/javascript",
        "text/typescript", "application/typescript",
        "text/x-python", "text/x-java", "text/x-kotlin",
        "text/x-c", "text/x-cpp", "text/x-rust",
        "text/x-go", "text/x-ruby", "text/x-php"
    )
    return codeTypes.any { contentType.contains(it, ignoreCase = true) }
}

fun detectLanguage(contentType: String?, fileName: String): String {
    return when {
        contentType?.contains("javascript") == true -> "javascript"
        contentType?.contains("typescript") == true -> "typescript"
        contentType?.contains("python") == true -> "python"
        contentType?.contains("java") == true -> "java"
        contentType?.contains("kotlin") == true -> "kotlin"
        contentType?.contains("html") == true -> "html"
        contentType?.contains("css") == true -> "css"
        contentType?.contains("json") == true -> "json"
        contentType?.contains("yaml") == true || contentType?.contains("yml") == true -> "yaml"
        fileName.endsWith(".kt") -> "kotlin"
        fileName.endsWith(".java") -> "java"
        fileName.endsWith(".py") -> "python"
        fileName.endsWith(".js") -> "javascript"
        fileName.endsWith(".ts") -> "typescript"
        fileName.endsWith(".tsx") -> "typescript"
        fileName.endsWith(".jsx") -> "javascript"
        fileName.endsWith(".html") -> "html"
        fileName.endsWith(".css") -> "css"
        fileName.endsWith(".json") -> "json"
        fileName.endsWith(".yaml") || fileName.endsWith(".yml") -> "yaml"
        else -> "text"
    }
}
```

---

## 十、网络状态反馈升级

### 10.1 现状问题

```kotlin
// 当前实现：只有一个进度条
if (state.isRefreshingTasks) {
    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
}
```

问题：
- 没有网络错误重试按钮
- 没有离线模式提示
- 没有连接状态指示器
- 没有请求超时提示
- 没有后台同步状态

### 10.2 升级方案

```kotlin
// 网络状态数据类
data class NetworkState(
    val isConnected: Boolean,
    val connectionType: ConnectionType,
    val lastSyncTime: Long?,
    val pendingSyncCount: Int,
    val errorMessage: String?,
)

enum class ConnectionType {
    WIFI, CELLULAR, ETHERNET, UNKNOWN, OFFLINE
}

// 全局网络状态组件
@Composable
fun NetworkStatusBanner(
    networkState: NetworkState,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = !networkState.isConnected || networkState.errorMessage != null,
        enter = expandVertically(),
        exit = shrinkVertically(),
        modifier = modifier
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = when {
                !networkState.isConnected -> MaterialTheme.colorScheme.errorContainer
                networkState.errorMessage != null -> MaterialTheme.colorScheme.errorContainer
                else -> MaterialTheme.colorScheme.primaryContainer
            }
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    when {
                        !networkState.isConnected -> Icons.Filled.WifiOff
                        networkState.errorMessage != null -> Icons.Filled.Error
                        else -> Icons.Filled.Wifi
                    },
                    contentDescription = null,
                    tint = when {
                        !networkState.isConnected -> MaterialTheme.colorScheme.error
                        networkState.errorMessage != null -> MaterialTheme.colorScheme.error
                        else -> MaterialTheme.colorScheme.primary
                    }
                )
                
                Spacer(Modifier.width(12.dp))
                
                Column(Modifier.weight(1f)) {
                    Text(
                        when {
                            !networkState.isConnected -> "网络已断开"
                            networkState.errorMessage != null -> networkState.errorMessage
                            else -> "网络已连接"
                        },
                        style = MaterialTheme.typography.bodyMedium
                    )
                    
                    networkState.pendingSyncCount.takeIf { it > 0 }?.let { count ->
                        Text(
                            "$count 个操作等待同步",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
                
                if (networkState.errorMessage != null) {
                    TextButton(onClick = onRetry) {
                        Text("重试")
                    }
                }
            }
        }
    }
}

// 加载状态组件
@Composable
fun LoadingStateView(
    message: String = "加载中...",
    progress: Float? = null,
    onCancel: (() -> Unit)? = null,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        if (progress != null) {
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth(0.6f)
            )
        } else {
            CircularProgressIndicator()
        }
        
        Spacer(Modifier.height(16.dp))
        Text(message, style = MaterialTheme.typography.bodyMedium)
        
        onCancel?.let {
            Spacer(Modifier.height(16.dp))
            TextButton(onClick = it) {
                Text("取消")
            }
        }
    }
}

// 错误状态组件
@Composable
fun ErrorStateView(
    title: String = "出错了",
    message: String,
    errorType: ErrorType = ErrorType.UNKNOWN,
    onRetry: (() -> Unit)? = null,
    onDismiss: (() -> Unit)? = null,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            errorType.icon,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.error
        )
        
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge)
        
        Spacer(Modifier.height(8.dp))
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center
        )
        
        errorType.suggestion?.let { suggestion ->
            Spacer(Modifier.height(16.dp))
            SuggestionCard(suggestion = suggestion)
        }
        
        Spacer(Modifier.height(24.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            onDismiss?.let {
                OutlinedButton(onClick = it) {
                    Text("关闭")
                }
            }
            onRetry?.let {
                Button(onClick = it) {
                    Icon(Icons.Filled.Refresh, null)
                    Spacer(Modifier.width(8.dp))
                    Text("重试")
                }
            }
        }
    }
}

enum class ErrorType(
    val icon: ImageVector,
    val suggestion: String?,
) {
    NETWORK(
        icon = Icons.Filled.WifiOff,
        suggestion = "请检查网络连接后重试"
    ),
    SERVER(
        icon = Icons.Filled.CloudOff,
        suggestion = "服务器暂时不可用，请稍后重试"
    ),
    AUTH(
        icon = Icons.Filled.Lock,
        suggestion = "登录已过期，请重新登录"
    ),
    TIMEOUT(
        icon = Icons.Filled.Timer,
        suggestion = "请求超时，请检查网络后重试"
    ),
    UNKNOWN(
        icon = Icons.Filled.Error,
        suggestion = null
    );
}

@Composable
fun SuggestionCard(suggestion: String) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Filled.Lightbulb,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSecondaryContainer
            )
            Spacer(Modifier.width(8.dp))
            Text(
                suggestion,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSecondaryContainer
            )
        }
    }
}

// 空状态组件
@Composable
fun EmptyStateView(
    title: String,
    message: String,
    icon: ImageVector = Icons.Filled.Inbox,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(80.dp),
            tint = MaterialTheme.colorScheme.outline
        )
        
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge)
        
        Spacer(Modifier.height(8.dp))
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(24.dp))
            Button(onClick = onAction) {
                Text(actionLabel)
            }
        }
    }
}
```

---

## 十一、深色模式支持

### 11.1 现状问题

当前代码没有深色模式支持。

### 11.2 升级方案

```kotlin
// 主题配置
data class AppTheme(
    val darkMode: DarkMode,
    val useDynamicColors: Boolean,
    val primaryColor: Color?,
)

enum class DarkMode {
    SYSTEM, LIGHT, DARK
}

// 主题管理
class ThemeManager(private val context: Context) {
    private val dataStore = context.dataStore
    
    val themeFlow: Flow<AppTheme> = dataStore.data.map { prefs ->
        AppTheme(
            darkMode = DarkMode.valueOf(
                prefs[DARK_MODE_KEY] ?: DarkMode.SYSTEM.name
            ),
            useDynamicColors = prefs[DYNAMIC_COLORS_KEY] ?: true,
            primaryColor = prefs[PRIMARY_COLOR_KEY]?.let { Color(it) }
        )
    }
    
    suspend fun setDarkMode(mode: DarkMode) {
        dataStore.edit { prefs ->
            prefs[DARK_MODE_KEY] = mode.name
        }
    }
    
    suspend fun setDynamicColors(enabled: Boolean) {
        dataStore.edit { prefs ->
            prefs[DYNAMIC_COLORS_KEY] = enabled
        }
    }
}

// 应用主题
@Composable
fun AutoCodeTheme(
    theme: AppTheme,
    content: @Composable () -> Unit,
) {
    val darkTheme = when (theme.darkMode) {
        DarkMode.SYSTEM -> isSystemInDarkTheme()
        DarkMode.LIGHT -> false
        DarkMode.DARK -> true
    }
    
    val colorScheme = when {
        theme.useDynamicColors && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> darkColorScheme(
            primary = theme.primaryColor ?: Color(0xFF8AB4F8),
            secondary = Color(0xFF81C995),
            tertiary = Color(0xFFF28B82),
            background = Color(0xFF1F1F1F),
            surface = Color(0xFF2D2D2D),
            error = Color(0xFFF28B82)
        )
        else -> lightColorScheme(
            primary = theme.primaryColor ?: Color(0xFF1A73E8),
            secondary = Color(0xFF34A853),
            tertiary = Color(0xFFEA4335),
            background = Color(0xFFFFFBFE),
            surface = Color(0xFFFFFBFE),
            error = Color(0xFFB3261E)
        )
    }
    
    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}

// 设置页面主题选择
@Composable
fun ThemeSettingsSection(
    currentTheme: AppTheme,
    onThemeChange: (AppTheme) -> Unit,
) {
    Column {
        Text("外观", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(16.dp))
        
        // 深色模式选择
        Text("深色模式", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        
        DarkModeSelector(
            selected = currentTheme.darkMode,
            onSelect = { mode ->
                onThemeChange(currentTheme.copy(darkMode = mode))
            }
        )
        
        Spacer(Modifier.height(16.dp))
        
        // 动态颜色开关
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("动态颜色", style = MaterialTheme.typography.labelLarge)
                    Text(
                        "根据壁纸自动调整应用颜色",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                Switch(
                    checked = currentTheme.useDynamicColors,
                    onCheckedChange = { enabled ->
                        onThemeChange(currentTheme.copy(useDynamicColors = enabled))
                    }
                )
            }
        }
    }
}

@Composable
fun DarkModeSelector(
    selected: DarkMode,
    onSelect: (DarkMode) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        DarkModeOption(
            label = "跟随系统",
            icon = Icons.Filled.BrightnessAuto,
            selected = selected == DarkMode.SYSTEM,
            onClick = { onSelect(DarkMode.SYSTEM) }
        )
        DarkModeOption(
            label = "浅色",
            icon = Icons.Filled.LightMode,
            selected = selected == DarkMode.LIGHT,
            onClick = { onSelect(DarkMode.LIGHT) }
        )
        DarkModeOption(
            label = "深色",
            icon = Icons.Filled.DarkMode,
            selected = selected == DarkMode.DARK,
            onClick = { onSelect(DarkMode.DARK) }
        )
    }
}

@Composable
fun DarkModeOption(
    label: String,
    icon: ImageVector,
    selected: Boolean,
    onClick: () -> Unit,
) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label) },
        leadingIcon = {
            Icon(
                icon,
                contentDescription = null,
                modifier = Modifier.size(18.dp)
            )
        }
    )
}
```

---

## 十二、国际化支持

### 12.1 现状问题

```kotlin
// 当前实现：硬编码中文字符串
Text("首页")
Text("任务")
Text("项目")
Text("我的")
```

### 12.2 升级方案

```kotlin
// 字符串资源文件结构
// res/values/strings.xml (中文)
// res/values-en/strings.xml (英文)

// strings.xml
<resources>
    <string name="app_name">AutoCode</string>
    <string name="tab_work">工作</string>
    <string name="tab_history">历史</string>
    <string name="tab_artifacts">产物</string>
    <string name="tab_settings">设置</string>
    
    <string name="login_title">登录</string>
    <string name="login_server_address">服务器地址</string>
    <string name="login_username">用户名</string>
    <string name="login_password">密码</string>
    <string name="login_connect">连接</string>
    <string name="login_test_connection">测试连接</string>
    
    <string name="task_create_title">创建任务</string>
    <string name="task_prompt_label">需求描述</string>
    <string name="task_prompt_placeholder">描述你想要创建的应用或功能…</string>
    <string name="task_submit">创建任务</string>
    
    <string name="error_network">网络连接失败</string>
    <string name="error_server">服务器错误</string>
    <string name="error_timeout">请求超时</string>
    
    <string name="empty_no_tasks">暂无任务</string>
    <string name="empty_no_artifacts">暂无产物</string>
</resources>

// strings.xml (英文)
<resources>
    <string name="app_name">AutoCode</string>
    <string name="tab_work">Work</string>
    <string name="tab_history">History</string>
    <string name="tab_artifacts">Artifacts</string>
    <string name="tab_settings">Settings</string>
    
    <string name="login_title">Login</string>
    <string name="login_server_address">Server Address</string>
    <string name="login_username">Username</string>
    <string name="login_password">Password</string>
    <string name="login_connect">Connect</string>
    <string name="login_test_connection">Test Connection</string>
    
    <string name="task_create_title">Create Task</string>
    <string name="task_prompt_label">Description</string>
    <string name="task_prompt_placeholder">Describe the app or feature you want to create…</string>
    <string name="task_submit">Create Task</string>
    
    <string name="error_network">Network connection failed</string>
    <string name="error_server">Server error</string>
    <string name="error_timeout">Request timeout</string>
    
    <string name="empty_no_tasks">No tasks yet</string>
    <string name="empty_no_artifacts">No artifacts yet</string>
</resources>

// 使用字符串资源
@Composable
fun LocalizedText(
    @StringRes resId: Int,
    modifier: Modifier = Modifier,
    style: TextStyle = LocalTextStyle.current
) {
    Text(
        text = stringResource(resId),
        modifier = modifier,
        style = style
    )
}

// 语言设置
data class LanguageConfig(
    val currentLanguage: String,
    val availableLanguages: List<Language>,
)

data class Language(
    val code: String,
    val name: String,
    val nativeName: String,
)

@Composable
fun LanguageSelector(
    currentLanguage: String,
    onSelect: (String) -> Unit,
) {
    val languages = listOf(
        Language("zh", "Chinese", "中文"),
        Language("en", "English", "English"),
    )
    
    Column {
        Text("语言 / Language", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        
        languages.forEach { language ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelect(language.code) }
                    .padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                RadioButton(
                    selected = currentLanguage == language.code,
                    onClick = { onSelect(language.code) }
                )
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(language.nativeName, style = MaterialTheme.typography.bodyLarge)
                    Text(language.name, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
```

---

## 十三、性能优化

### 13.1 现状问题

```kotlin
// 当前实现：每次重组都重新排序
val events = state.taskEvents[taskId].orEmpty().sortedBy { it.seq }
```

问题：
- 没有列表分页
- 没有图片懒加载
- 没有内存缓存策略
- 没有后台任务优化

### 13.2 升级方案

```kotlin
// 1. 使用 remember 缓存计算结果
@Composable
fun TaskDetailScreen(vm: AppViewModel, taskId: String) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    
    // 使用 remember 缓存排序结果
    val sortedEvents = remember(state.taskEvents[taskId]) {
        state.taskEvents[taskId].orEmpty().sortedBy { it.seq }
    }
    
    // ...
}

// 2. 分页加载
data class PaginatedEvents(
    val events: List<TaskEventDto>,
    val hasMore: Boolean,
    val page: Int,
    val pageSize: Int = 50,
)

class EventPager(
    private val allEvents: List<TaskEventDto>,
    private val pageSize: Int = 50,
) {
    private var currentPage = 0
    
    val hasMore: Boolean
        get() = (currentPage + 1) * pageSize < allEvents.size
    
    fun loadNextPage(): List<TaskEventDto> {
        val start = currentPage * pageSize
        val end = minOf(start + pageSize, allEvents.size)
        currentPage++
        return allEvents.subList(start, end)
    }
    
    fun reset() {
        currentPage = 0
    }
}

// 3. 图片懒加载配置
@Composable
fun AppImageLoader() {
    val imageLoader = ImageLoader.Builder(LocalContext.current)
        .memoryCache {
            MemoryCache.Builder(LocalContext.current)
                .maxSizePercent(0.25) // 使用 25% 的内存
                .build()
        }
        .diskCache {
            DiskCache.Builder()
                .directory(LocalContext.current.cacheDir.resolve("image_cache"))
                .maxSizeBytes(512L * 1024 * 1024) // 512MB
                .build()
        }
        .build()
    
    Coil.setImageLoader(imageLoader)
}

// 4. 列表优化
@Composable
fun OptimizedEventList(
    events: List<TaskEventDto>,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier,
        // 启用项目预加载
        contentPadding = PaddingValues(16.dp),
        // 设置固定高度项目的高度（如果适用）
        // itemContentType = { event -> event.type }
    ) {
        items(
            items = events,
            key = { event -> eventStableKey(event{}
            },
            // 指定内容类型以优化复用
            contentType = { event -> event.type }
        ) { event ->
            // 使用 key 确保正确的重组
            AgentEventItem(
                event = event,
                fallbackLine = eventLineProvider(event)
            )
        }
    }
}

// 5. ViewModel 优化
class AppViewModel(application: Application) : AndroidViewModel(application) {
    // 使用缓存的事件列表
    private val _cachedEvents = mutableMapOf<String, List<TaskEventDto>>()
    
    fun getEventsForTask(taskId: String): List<TaskEventDto> {
        return _cachedEvents.getOrPut(taskId) {
            _uiState.value.taskEvents[taskId].orEmpty().sortedBy { it.seq }
        }
    }
    
    // 清理缓存
    fun clearEventCache(taskId: String) {
        _cachedEvents.remove(taskId)
    }
}
```

---

## 十四、无障碍支持

### 14.1 现状问题

当前代码没有无障碍支持：
- 没有内容描述
- 没有屏幕阅读器支持
- 没有字体缩放适配
- 没有高对比度模式

### 14.2 升级方案

```kotlin
// 1. 添加内容描述
@Composable
fun AccessibleIconButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    contentDescription: String?,
    enabled: Boolean = true,
    icon: @Composable () -> Unit,
) {
    IconButton(
        onClick = onClick,
        modifier = modifier
            .semantics {
                this.contentDescription = contentDescription ?: ""
                this.enabled = enabled
            },
        enabled = enabled
    ) {
        icon()
    }
}

// 2. 屏幕阅读器优化
@Composable
fun AccessibleTaskCard(
    task: TaskItem,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .clickable(onClick = onClick)
            .semantics {
                // 自定义屏幕阅读器播报内容
                contentDescription = buildString {
                    append("任务：${task.prompt}")
                    append("，状态：${taskStatusLabel(task.status)}")
                    append("，进度：${task.progress}%")
                }
                // 标记为按钮
                role = Role.Button
            }
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(task.prompt, maxLines = 2)
            Spacer(Modifier.height(6.dp))
            Text("${taskStatusLabel(task.status)} · ${task.progress}%")
        }
    }
}

// 3. 字体缩放适配
@Composable
fun ScalableText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = LocalTextStyle.current,
    maxLines: Int = Int.MAX_VALUE,
) {
    val density = LocalDensity.current
    val fontScale = LocalConfiguration.current.fontScale
    
    // 限制最大缩放比例
    val adjustedStyle = remember(fontScale, style) {
        if (fontScale > 1.5f) {
            style.copy(fontSize = style.fontSize * 1.5f / fontScale)
        } else {
            style
        }
    }
    
    Text(
        text = text,
        modifier = modifier,
        style = adjustedStyle,
        maxLines = maxLines,
        overflow = TextOverflow.Ellipsis
    )
}

// 4. 高对比度模式
@Composable
fun HighContrastAwareCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val isHighContrast = LocalInspectionMode.value // 或检测系统设置
    
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = if (isHighContrast) {
                Color.White
            } else {
                MaterialTheme.colorScheme.surface
            }
        ),
        border = if (isHighContrast) {
            BorderStroke(2.dp, Color.Black)
        } else {
            null
        }
    ) {
        content()
    }
}

// 5. 焦点管理
@Composable
fun FocusableTaskItem(
    task: TaskItem,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var isFocused by remember { mutableStateOf(false) }
    
    Card(
        modifier = modifier
            .clickable(onClick = onClick)
            .focusable()
            .onFocusEvent { focusState ->
                isFocused = focusState.isFocused
            }
            .border(
                width = if (isFocused) 2.dp else 0.dp,
                color = if (isFocused) MaterialTheme.colorScheme.primary else Color.Transparent
            )
    ) {
        // 内容
    }
}
```

---

## 十五、实施路线图

### 15.1 分阶段实施

| 阶段 | 内容 | 优先级 | 预计工时 |
|------|------|--------|----------|
| P0 | 信息架构重构（4个Tab） | 高 | 3天 |
| P0 | 登录流程升级 | 高 | 2天 |
| P0 | 任务创建升级 | 高 | 3天 |
| P1 | 首页升级为工作台 | 中 | 2天 |
| P1 | 任务详情页升级 | 中 | 3天 |
| P1 | 审批交互升级 | 中 | 2天 |
| P2 | 语音输入升级 | 中 | 2天 |
| P2 | 产物预览升级 | 中 | 3天 |
| P2 | 网络状态反馈 | 中 | 1天 |
| P3 | 深色模式 | 低 | 2天 |
| P3 | 国际化 | 低 | 3天 |
| P3 | 无障碍支持 | 低 | 2天 |
| P3 | 性能优化 | 低 | 2天 |

### 15.2 技术依赖

```gradle
// build.gradle.kts 新增依赖
dependencies {
    // Markdown 渲染
    implementation("com.mikepenz:multiplatform-markdown-renderer:0.12.0")
    
    // 图片加载
    implementation("io.coil-kt:coil-compose:2.5.0")
    
    // 代码高亮
    implementation("com.github.AhmedMourad0:Noob-CodeView:1.0.0")
    
    // WebView
    implementation("androidx.webkit:webkit:1.8.0")
    
    // DataStore
    implementation("androidx.datastore:datastore-preferences:1.0.0")
    
    // 语音识别增强
    implementation("com.google.android.gms:play-services-mlkit-text-recognition:19.0.0")
}
```

### 15.3 测试策略

```kotlin
// UI 测试示例
@Test
fun testLoginFlow() {
    composeTestRule.setContent {
        EnhancedLoginScreen(
            config = LoginConfig(
                presetServers = listOf(
                    PresetServer("1", "测试环境", "https://test.example.com")
                ),
                recentServers = emptyList()
            ),
            onServerSelect = {},
            onManualInput = {},
            onQrCodeScan = {}
        )
    }
    
    // 验证预设服务器显示
    composeTestRule.onNodeWithText("测试环境").assertIsDisplayed()
    
    // 验证手动输入入口
    composeTestRule.onNodeWithText("手动输入服务器地址").assertIsDisplayed()
}

@Test
fun testTaskCreation() {
    composeTestRule.setContent {
        TaskCreationScreen(
            vm = testViewModel,
            templateId = null,
            onCreated = {},
            onBack = {}
        )
    }
    
    // 验证模板选择器
    composeTestRule.onNodeWithText("选择模板").assertIsDisplayed()
    
    // 验证需求输入
    composeTestRule.onNodeWithText("需求描述").assertIsDisplayed()
    
    // 验证提交按钮初始状态
    composeTestRule.onNodeWithText("创建任务").assertIsNotEnabled()
}
```

---

## 十六、总结

本升级方案针对用户反馈的15个核心问题，从以下维度进行了系统性改进：

1. **信息架构**：从5个Tab精简为4个，功能更清晰
2. **登录流程**：增加预设服务器、历史连接、扫码配置、连接测试
3. **首页升级**：从只读文本变为工作台，增加快捷操作、统计、模板
4. **任务创建**：增加模板选择、需求引导、附件上传、语音输入
5. **语音输入**：增加实时反馈、结果编辑、重试机制
6. **任务详情**：增加事件筛选、搜索、分页、错误高亮
7. **审批交互**：增加风险等级、命令详情、历史参考、倒计时
8. **产物预览**：增加代码高亮、图片预览、HTML渲染、JSON格式化
9. **网络状态**：增加连接状态指示、错误重试、离线提示
10. **深色模式**：支持系统跟随、手动切换、动态颜色
11. **国际化**：支持中英文切换，字符串资源化
12. **性能优化**：列表分页、图片缓存、计算缓存
13. **无障碍**：内容描述、屏幕阅读器、字体缩放、高对比度

预计总工时：30人天，建议分3个迭代完成：
- 迭代1（P0）：核心流程优化，10天
- 迭代2（P1）：体验提升，8天
- 迭代3（P2-P3）：完善功能，12天
