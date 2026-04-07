package com.autocode.mobile

import android.Manifest
import android.app.Application
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.autocode.mobile.network.ArtifactListItem
import com.autocode.mobile.network.TaskEventDto
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.PermissionStatus
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull

private sealed class Tab(
    val route: String,
    val label: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
) {
    data object Home : Tab("home", "首页", Icons.Filled.Home)
    data object Tasks : Tab("tasks", "任务", Icons.Filled.List)
    data object Projects : Tab("projects", "项目", Icons.Filled.Folder)
    data object Account : Tab("account", "我的", Icons.Filled.Person)
    data object Artifacts : Tab("artifacts", "产物", Icons.Filled.AttachFile)
}

@Composable
fun AutoCodeApp() {
    val app = LocalContext.current.applicationContext as Application
    val vm: AppViewModel = viewModel(factory = AppViewModelFactory.create(app))
    val state by vm.uiState.collectAsStateWithLifecycle()
    val nav = rememberNavController()

    if (state.isLoading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }

    val start = if (state.session != null) "shell" else "login"

    NavHost(navController = nav, startDestination = start) {
        composable("login") {
            LoginRoute(vm = vm)
        }
        composable("shell") {
            MainShell(vm = vm)
        }
    }

    LaunchedEffect(state.session, state.isLoading) {
        if (state.isLoading) return@LaunchedEffect
        val dest = nav.currentBackStackEntry?.destination?.route
        if (state.session != null && dest == "login") {
            nav.navigate("shell") {
                popUpTo(nav.graph.findStartDestination().id) { inclusive = true }
            }
        }
        if (state.session == null && dest == "shell") {
            nav.navigate("login") {
                popUpTo(nav.graph.findStartDestination().id) { inclusive = true }
            }
        }
    }
}
@Composable
private fun LoginRoute(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var user by rememberSaveable { mutableStateOf("") }
    var pass by rememberSaveable { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = "AutoCode")
        Spacer(Modifier.height(8.dp))
        Text(
            text = "在「我的」填写控制面 Base URL 后，将使用 JWT 登录与创建任务；" +
                "留空则离线模拟。",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = user,
            onValueChange = { user = it },
            label = { Text("用户名") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = pass,
            onValueChange = { pass = it },
            label = { Text("密码") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        state.errorMessage?.let { msg ->
            Spacer(Modifier.height(8.dp))
            Text(text = msg, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = {
                vm.consumeError()
                vm.login(user, pass)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("登录")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainShell(vm: AppViewModel) {
    val innerNav = rememberNavController()
    val navBackStackEntry by innerNav.currentBackStackEntryAsState()
    val current = navBackStackEntry?.destination?.route.orEmpty()
    val showBar =
        current in
            listOf(
                Tab.Home.route,
                Tab.Tasks.route,
                Tab.Projects.route,
                Tab.Account.route,
                Tab.Artifacts.route,
            )

    Scaffold(
        bottomBar = {
            if (showBar) {
                NavigationBar {
                    val tabs = listOf(Tab.Home, Tab.Tasks, Tab.Artifacts, Tab.Projects, Tab.Account)
                    tabs.forEach { tab ->
                        val selected = current == tab.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                innerNav.navigate(tab.route) {
                                    popUpTo(innerNav.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = innerNav,
            startDestination = Tab.Home.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Tab.Home.route) {
                HomeTab(vm)
            }
            composable(Tab.Tasks.route) {
                TaskListTab(vm, innerNav)
            }
            composable(
                route = "task/{id}",
                arguments = listOf(navArgument("id") { type = NavType.StringType }),
            ) { entry ->
                val id = entry.arguments?.getString("id").orEmpty()
                TaskDetailTab(
                    vm,
                    taskId = id,
                    onBack = { innerNav.popBackStack() },
                    innerNav = innerNav,
                )
            }
            composable(Tab.Artifacts.route) {
                ArtifactsHubTab(vm, innerNav)
            }
            composable(
                route = "artifacts/history",
            ) {
                PublishHistoryScreen(vm, onBack = { innerNav.popBackStack() })
            }
            composable(
                route = "artifacts/task/{taskId}",
                arguments = listOf(navArgument("taskId") { type = NavType.StringType }),
            ) { entry ->
                val tid = entry.arguments?.getString("taskId").orEmpty()
                ArtifactsForTaskScreen(
                    vm,
                    taskId = tid,
                    onBack = { innerNav.popBackStack() },
                    innerNav = innerNav,
                )
            }
            composable(
                route = "artifacts/item/{taskId}/{artifactId}",
                arguments =
                    listOf(
                        navArgument("taskId") { type = NavType.StringType },
                        navArgument("artifactId") { type = NavType.StringType },
                    ),
            ) { entry ->
                val tid = entry.arguments?.getString("taskId").orEmpty()
                val aid = entry.arguments?.getString("artifactId").orEmpty()
                ArtifactDetailScreen(
                    vm,
                    taskId = tid,
                    artifactId = aid,
                    onBack = { innerNav.popBackStack() },
                )
            }
            composable(Tab.Projects.route) {
                ProjectsTab(vm)
            }
            composable(Tab.Account.route) {
                AccountTab(vm)
            }
        }
    }
}

@Composable
private fun HomeTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val project = state.dynamicProjects.find { it.id == state.selectedProjectId }
    val mode =
        if (state.baseUrl.isBlank()) {
            "离线模拟（未配置控制面 URL）"
        } else {
            "已配置控制面：${state.baseUrl}"
        }
    Column(Modifier.padding(20.dp)) {
        Text("首页", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text("已登录：${state.session?.displayName ?: "—"}")
        Spacer(Modifier.height(8.dp))
        Text("当前项目：${project?.name ?: state.selectedProjectId ?: "未选择"}")
        Spacer(Modifier.height(8.dp))
        Text("生成目标：${state.generationTarget.displayLabel()}")
        Spacer(Modifier.height(8.dp))
        Text(mode, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(20.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text(
                    "PR-1：登录、会话、项目、生成目标。\n" +
                        "PR-2：自然语言任务 + 控制面轮询或本地模拟。\n" +
                        "PR-3：「产物」Tab 列表/详情、预览与发布入口（占位）、发布历史。",
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
private fun TaskListTab(vm: AppViewModel, nav: NavHostController) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var prompt by rememberSaveable { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val audioPermissionState = rememberPermissionState(Manifest.permission.RECORD_AUDIO)
    var askedAudioPermission by rememberSaveable { mutableStateOf(false) }
    var voiceHint by rememberSaveable { mutableStateOf<String?>(null) }
    val list = vm.tasksForCurrentProject()
    val project = state.dynamicProjects.find { it.id == state.selectedProjectId }
    val permissionRationale =
        (audioPermissionState.status as? PermissionStatus.Denied)?.shouldShowRationale == true
    val voiceInputLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val text =
                result.data
                    ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    ?.firstOrNull()
                    ?.trim()
                    .orEmpty()
            if (text.isNotEmpty()) {
                prompt = if (prompt.isBlank()) text else "$prompt\n$text"
                voiceHint = null
            }
        }

    fun startVoiceInput() {
        val intent = buildSpeechRecognizerIntent()
        if (intent.resolveActivity(context.packageManager) == null) {
            voiceHint = "当前设备不支持语音识别"
            return
        }
        runCatching { voiceInputLauncher.launch(intent) }
            .onFailure { voiceHint = "语音识别启动失败，请稍后重试" }
    }

    if (state.selectedProjectId == null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("请先在「项目」页选择项目。")
        }
        return
    }

    Column(Modifier.padding(16.dp)) {
        TopAppBar(title = { Text("任务") })
        Text(
            "当前项目：${project?.name ?: state.selectedProjectId}",
            modifier = Modifier.padding(bottom = 12.dp),
        )
        Row(verticalAlignment = Alignment.Top) {
            OutlinedTextField(
                value = prompt,
                onValueChange = { prompt = it },
                label = { Text("自然语言描述") },
                modifier = Modifier
                    .weight(1f)
                    .height(140.dp),
                minLines = 4,
            )
            Spacer(Modifier.width(8.dp))
            VoiceInputButton(
                permissionGranted = audioPermissionState.status.isGranted,
                onStartVoiceInput = { startVoiceInput() },
                onRequestPermission = {
                    askedAudioPermission = true
                    audioPermissionState.launchPermissionRequest()
                },
            )
        }
        if (askedAudioPermission && !audioPermissionState.status.isGranted) {
            val tip =
                if (permissionRationale) {
                    "请允许麦克风权限后再使用语音输入"
                } else {
                    "未授予麦克风权限，语音输入不可用"
                }
            Text(
                tip,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        voiceHint?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        state.errorMessage?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                vm.consumeError()
                scope.launch {
                    val id = vm.createTaskAsync(prompt)
                    if (id != null) {
                        prompt = ""
                        nav.navigate("task/$id")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("发起任务")
        }
        Spacer(Modifier.height(16.dp))
        Text("任务列表", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(list, key = { it.id }) { t ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { nav.navigate("task/${t.id}") },
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(t.prompt, maxLines = 2)
                        Spacer(Modifier.height(6.dp))
                        Text("${t.source.name} · ${t.status.name} · ${t.progress}%")
                    }
                }
            }
        }
    }
}

@Composable
private fun VoiceInputButton(
    permissionGranted: Boolean,
    onStartVoiceInput: () -> Unit,
    onRequestPermission: () -> Unit,
) {
    IconButton(
        onClick = {
            if (permissionGranted) onStartVoiceInput() else onRequestPermission()
        },
        modifier = Modifier.padding(top = 4.dp),
    ) {
        Icon(Icons.Filled.Mic, contentDescription = "语音输入")
    }
}

private fun buildSpeechRecognizerIntent(): Intent =
    Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        putExtra(RecognizerIntent.EXTRA_PROMPT, "请说出你的任务描述")
    }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskDetailTab(
    vm: AppViewModel,
    taskId: String,
    onBack: () -> Unit,
    innerNav: NavHostController,
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val pendingApproval by vm.pendingApproval.collectAsStateWithLifecycle()
    val task = state.tasks.find { it.id == taskId }
    val events = state.taskEvents[taskId].orEmpty().sortedBy { it.seq }
    val eventsListState = rememberLazyListState()
    val approvalForTask = pendingApproval?.takeIf { it.taskId == taskId }

    LaunchedEffect(taskId, state.baseUrl, state.session?.accessToken) {
        vm.subscribeTaskEvents(taskId)
    }
    LaunchedEffect(events.size) {
        if (events.isNotEmpty()) {
            runCatching { eventsListState.animateScrollToItem(events.lastIndex) }
        }
    }
    DisposableEffect(taskId) {
        onDispose { vm.unsubscribeTaskEvents(taskId) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("任务详情") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { pad ->
        if (task == null) {
            Box(
                Modifier
                    .fillMaxSize()
                    .padding(pad),
                contentAlignment = Alignment.Center,
            ) {
                Text("任务不存在")
            }
            return@Scaffold
        }
        Column(
            Modifier
                .padding(pad)
                .padding(16.dp)
                .fillMaxSize(),
        ) {
            Text(task.prompt, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            Text("来源：${task.source.name}（LOCAL=本地模拟，REMOTE=控制面轮询）")
            Text("状态：${task.status.name}")
            Text("进度：${task.progress}%")
            Spacer(Modifier.height(12.dp))
            LinearProgressIndicator(
                progress = { task.progress / 100f },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(20.dp))
            Text(
                if (task.source == TaskSource.REMOTE) "事件流（实时）" else "执行日志（本地模拟）",
                style = MaterialTheme.typography.titleSmall,
            )
            Spacer(Modifier.height(8.dp))
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                state = eventsListState,
            ) {
                if (events.isNotEmpty()) {
                    items(events, key = { eventStableKey(it) }) { event ->
                        AgentEventItem(event = event, fallbackLine = vm.eventLine(event))
                    }
                } else {
                    items(task.logs) { line ->
                        Card(
                            colors =
                                CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant,
                                ),
                        ) {
                            Text(
                                text = line,
                                modifier = Modifier.padding(12.dp),
                                fontFamily = FontFamily.Monospace,
                            )
                        }
                    }
                }
            }
            if (task.status == TaskStatus.SUCCEEDED) {
                Spacer(Modifier.height(20.dp))
                TextButton(
                    onClick = { innerNav.navigate("artifacts/task/${task.id}") },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("查看产物（PR-3）")
                }
            }
        }
    }

    approvalForTask?.let { approval ->
        ApprovalBottomSheet(
            approval = approval,
            onApprove = { comment ->
                vm.submitApproval(
                    taskId = approval.taskId,
                    approvalId = approval.approvalId,
                    decision = "approve",
                    comment = comment,
                )
            },
            onReject = { comment ->
                vm.submitApproval(
                    taskId = approval.taskId,
                    approvalId = approval.approvalId,
                    decision = "reject",
                    comment = comment,
                )
            },
            onTimeout = {
                vm.dismissPendingApproval(taskId = approval.taskId, approvalId = approval.approvalId)
            },
            onDismiss = {
                vm.dismissPendingApproval(taskId = approval.taskId, approvalId = approval.approvalId)
            },
        )
    }
}

@Composable
private fun AgentEventItem(event: TaskEventDto, fallbackLine: String) {
    val type = event.type?.uppercase().orEmpty()
    val payload = event.payload
    val header = "Seq ${event.seq} · ${event.type ?: "EVENT"}"

    when (type) {
        "ASSISTANT_OUTPUT" -> {
            val agent = payloadText(payload, "agent", "assistant", "assistantName") ?: "assistant"
            val message = payloadText(payload, "message", "content", "text", "output") ?: fallbackLine
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Filled.Person,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSecondaryContainer,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = "Agent: $agent",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSecondaryContainer,
                        )
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = header,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                    )
                }
            }
        }
        "TOOL_START" -> {
            val tool = payloadText(payload, "tool", "toolName") ?: "unknown"
            val command = payloadText(payload, "command", "cmd")
            val cwd = payloadText(payload, "cwd", "workdir")
            var expanded by rememberSaveable(eventStableKey(event)) { mutableStateOf(false) }
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("工具调用: $tool", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    if (!command.isNullOrBlank()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = command,
                            fontFamily = FontFamily.Monospace,
                            maxLines = if (expanded) Int.MAX_VALUE else 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    if (expanded && !cwd.isNullOrBlank()) {
                        Spacer(Modifier.height(6.dp))
                        Text("cwd: $cwd", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                    }
                    if (!command.isNullOrBlank() || !cwd.isNullOrBlank()) {
                        Spacer(Modifier.height(4.dp))
                        TextButton(onClick = { expanded = !expanded }) {
                            Text(if (expanded) "收起" else "展开")
                        }
                    }
                }
            }
        }
        "TOOL_END" -> {
            val status = payloadText(payload, "status", "result") ?: "unknown"
            val execMs = payloadLongValue(payload, "execMs", "elapsedMs", "durationMs")
            val success =
                status.equals("success", ignoreCase = true) ||
                    status.equals("ok", ignoreCase = true) ||
                    status.equals("done", ignoreCase = true)
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor =
                            if (success) MaterialTheme.colorScheme.primaryContainer
                            else MaterialTheme.colorScheme.errorContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        text = if (success) "工具执行完成" else "工具执行异常",
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text("状态: $status", fontFamily = FontFamily.Monospace)
                    execMs?.let {
                        Text("耗时: ${it}ms", fontFamily = FontFamily.Monospace)
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(header, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        "FILE_PATCH_PREVIEW" -> {
            val patch = payloadText(payload, "patch", "diff", "preview", "content")
            val lines = patch.orEmpty().lineSequence().take(120).toList()
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("代码变更预览", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(8.dp))
                    if (lines.isEmpty()) {
                        Text(fallbackLine, fontFamily = FontFamily.Monospace)
                    } else {
                        lines.forEach { line ->
                            val lineColor =
                                when {
                                    line.startsWith("+") -> Color(0xFF1B5E20)
                                    line.startsWith("-") -> Color(0xFFB71C1C)
                                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                                }
                            Text(
                                text = line,
                                color = lineColor,
                                fontFamily = FontFamily.Monospace,
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        if (patch != null && patch.lines().size > lines.size) {
                            Spacer(Modifier.height(6.dp))
                            Text("… 预览已截断", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
        "APPROVAL_REQUIRED" -> {
            val action = payloadText(payload, "action")
            val command = payloadText(payload, "command", "cmd")
            val reason = payloadText(payload, "reason")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("等待审批", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    action?.let {
                        Spacer(Modifier.height(6.dp))
                        Text("动作: $it")
                    }
                    command?.let {
                        Spacer(Modifier.height(6.dp))
                        Text("命令: $it", fontFamily = FontFamily.Monospace)
                    }
                    reason?.let {
                        Spacer(Modifier.height(6.dp))
                        Text("原因: $it")
                    }
                }
            }
        }
        "TASK_DONE", "TASK_FAILED" -> {
            val done = type == "TASK_DONE"
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor =
                            if (done) MaterialTheme.colorScheme.tertiaryContainer
                            else MaterialTheme.colorScheme.errorContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        text = if (done) "任务完成" else "任务失败",
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(fallbackLine)
                    Spacer(Modifier.height(6.dp))
                    Text(header, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        else -> {
            Card {
                Column(Modifier.padding(12.dp)) {
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text(fallbackLine, fontFamily = FontFamily.Monospace)
                }
            }
        }
    }
}

private fun eventStableKey(event: TaskEventDto): String =
    when {
        !event.eventId.isNullOrBlank() -> "id:${event.eventId}"
        event.seq > 0L -> "seq:${event.seq}"
        else -> "raw:${event.type}:${event.timestamp}:${event.payload}"
    }

private fun payloadText(payload: JsonObject, vararg keys: String): String? {
    keys.forEach { key ->
        val value =
            payload[key]
                ?.jsonPrimitive
                ?.contentOrNull
                ?.trim()
        if (!value.isNullOrEmpty()) return value
    }
    return null
}

private fun payloadLongValue(payload: JsonObject, vararg keys: String): Long? {
    keys.forEach { key ->
        val value = payload[key]?.jsonPrimitive?.longOrNull
        if (value != null) return value
    }
    return null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ApprovalBottomSheet(
    approval: ApprovalRequest,
    onApprove: (comment: String?) -> Unit,
    onReject: (comment: String?) -> Unit,
    onTimeout: () -> Unit,
    onDismiss: () -> Unit,
) {
    var comment by rememberSaveable(approval.approvalId) { mutableStateOf("") }
    var handling by remember(approval.approvalId) { mutableStateOf(false) }
    var secondsLeft by remember(approval.approvalId) { mutableStateOf(approval.timeoutSeconds.coerceAtLeast(1)) }
    val totalSeconds = approval.timeoutSeconds.coerceAtLeast(1)

    LaunchedEffect(approval.approvalId) {
        while (secondsLeft > 0 && !handling) {
            delay(1000)
            secondsLeft -= 1
        }
        if (secondsLeft <= 0 && !handling) {
            handling = true
            onTimeout()
        }
    }

    ModalBottomSheet(
        onDismissRequest = {
            if (handling) return@ModalBottomSheet
            handling = true
            onDismiss()
        },
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .verticalScroll(rememberScrollState()),
        ) {
            Text("审批请求", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(8.dp))
            Text("approvalId: ${approval.approvalId}", fontFamily = FontFamily.Monospace)
            approval.action?.let {
                Spacer(Modifier.height(6.dp))
                Text("action: $it")
            }
            approval.tool?.let {
                Spacer(Modifier.height(6.dp))
                Text("tool: $it")
            }
            approval.command?.let {
                Spacer(Modifier.height(6.dp))
                Text("command: $it", fontFamily = FontFamily.Monospace)
            }
            approval.cwd?.let {
                Spacer(Modifier.height(6.dp))
                Text("cwd: $it", fontFamily = FontFamily.Monospace)
            }
            approval.riskScore?.let {
                Spacer(Modifier.height(6.dp))
                Text("riskScore: ${String.format(Locale.getDefault(), "%.2f", it)}")
            }
            approval.reason?.let {
                Spacer(Modifier.height(6.dp))
                Text("reason: $it")
            }

            Spacer(Modifier.height(14.dp))
            Text("剩余 ${secondsLeft}s", style = MaterialTheme.typography.labelLarge)
            Spacer(Modifier.height(6.dp))
            LinearProgressIndicator(
                progress = { secondsLeft.toFloat() / totalSeconds.toFloat() },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(14.dp))
            OutlinedTextField(
                value = comment,
                onValueChange = { comment = it },
                label = { Text("审批备注（可选）") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )

            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = {
                        if (!handling) {
                            handling = true
                            onApprove(comment.takeIf { it.isNotBlank() })
                        }
                    },
                    enabled = !handling,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("批准")
                }
                Button(
                    onClick = {
                        if (!handling) {
                            handling = true
                            onReject(comment.takeIf { it.isNotBlank() })
                        }
                    },
                    enabled = !handling,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("拒绝")
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArtifactsHubTab(vm: AppViewModel, nav: NavHostController) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val done = vm.succeededTasksForCurrentProject()
    Column(Modifier.padding(16.dp)) {
        TopAppBar(title = { Text("产物") })
        Text(
            "选择已完成的任务查看上传产物；离线已完成任务显示占位文件。",
            style = MaterialTheme.typography.bodySmall,
        )
        Spacer(Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("发布与版本", style = MaterialTheme.typography.titleSmall)
            TextButton(onClick = { nav.navigate("artifacts/history") }) {
                Text("历史记录")
            }
        }
        Spacer(Modifier.height(8.dp))
        if (state.selectedProjectId == null) {
            Text("请先在「项目」页选择项目。")
            return@Column
        }
        if (done.isEmpty()) {
            Text("当前项目下暂无已完成任务。请先在「任务」页发起并等待完成。")
            return@Column
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(done, key = { it.id }) { t ->
                Card(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .clickable { nav.navigate("artifacts/task/${t.id}") },
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(t.prompt, maxLines = 2, style = MaterialTheme.typography.titleSmall)
                        Spacer(Modifier.height(6.dp))
                        Text("任务 ${t.id}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArtifactsForTaskScreen(
    vm: AppViewModel,
    taskId: String,
    onBack: () -> Unit,
    innerNav: NavHostController,
) {
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<ArtifactListItem>>(emptyList()) }
    var loadErr by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(taskId) {
        loading = true
        loadErr = null
        vm.loadArtifactsForTask(taskId).fold(
            onSuccess = { items = it },
            onFailure = { loadErr = it.message ?: "加载失败" },
        )
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("任务产物") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    TextButton(
                        onClick = {
                            scope.launch {
                                loading = true
                                vm.loadArtifactsForTask(taskId).fold(
                                    onSuccess = { items = it; loadErr = null },
                                    onFailure = { loadErr = it.message ?: "加载失败" },
                                )
                                loading = false
                            }
                        },
                    ) {
                        Text("刷新")
                    }
                },
            )
        },
    ) { pad ->
        Column(
            Modifier
                .padding(pad)
                .padding(16.dp)
                .fillMaxSize(),
        ) {
            Text("任务 ID：$taskId", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(12.dp))
            if (loading) {
                CircularProgressIndicator()
            } else {
                loadErr?.let {
                    Text(it, color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                }
                if (items.isEmpty()) {
                    Text("暂无产物（控制面列表为空或任务尚无上传）。")
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(items, key = { it.artifactId }) { a ->
                            Card(
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            innerNav.navigate(
                                                "artifacts/item/${a.taskId}/${a.artifactId}",
                                            )
                                        },
                            ) {
                                Column(Modifier.padding(14.dp)) {
                                    Text(a.name ?: a.artifactId, style = MaterialTheme.typography.titleSmall)
                                    Text(
                                        "${a.contentType ?: "—"} · ${a.sizeBytes ?: 0} bytes",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ArtifactDetailScreen(
    vm: AppViewModel,
    taskId: String,
    artifactId: String,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var art by remember { mutableStateOf<ArtifactListItem?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    var preview by remember { mutableStateOf<ArtifactPreview?>(null) }
    var previewErr by remember { mutableStateOf<String?>(null) }
    var previewLoading by remember { mutableStateOf(false) }
    var versionLabel by rememberSaveable(taskId, artifactId) { mutableStateOf(defaultVersionLabel()) }
    var publishHint by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(taskId, artifactId) {
        loading = true
        err = null
        art = null
        preview = null
        previewErr = null
        previewLoading = false
        versionLabel = defaultVersionLabel()
        publishHint = null
        vm.loadArtifactsForTask(taskId).fold(
            onSuccess = { list ->
                val found = list.find { it.artifactId == artifactId }
                if (found != null) {
                    art = found
                } else {
                    err = "未找到该产物"
                }
            },
            onFailure = { err = it.message ?: "加载失败" },
        )
        loading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("产物详情") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { pad ->
        Column(
            Modifier
                .padding(pad)
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
                .fillMaxSize(),
        ) {
            if (loading) {
                CircularProgressIndicator()
                return@Column
            }
            err?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
                return@Column
            }
            val a = art ?: return@Column
            Text(a.name ?: a.artifactId, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            Text("artifactId：${a.artifactId}")
            Text("contentType：${a.contentType ?: "—"}")
            Text("sizeBytes：${a.sizeBytes ?: "—"}")
            Text("sha256：${a.sha256 ?: "—"}", fontFamily = FontFamily.Monospace)
            Spacer(Modifier.height(20.dp))
            Text(
                "产物预览入口：支持文本类产物在线加载。",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    scope.launch {
                        previewLoading = true
                        previewErr = null
                        preview = null
                        vm.loadArtifactPreview(taskId, a).fold(
                            onSuccess = { preview = it },
                            onFailure = { previewErr = it.message ?: "加载预览失败" },
                        )
                        previewLoading = false
                    }
                },
                enabled = !previewLoading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (previewLoading) "加载预览中..." else "加载预览")
            }
            previewErr?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            preview?.let { p ->
                Spacer(Modifier.height(12.dp))
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(p.title, style = MaterialTheme.typography.titleSmall)
                        Text(
                            "${p.contentType ?: "text/plain"} · ${p.byteSize} bytes",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(p.content, fontFamily = FontFamily.Monospace)
                        if (p.truncated) {
                            Spacer(Modifier.height(8.dp))
                            Text("预览内容已截断，请下载完整文件查看。", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(
                "发布入口：填写版本号并记录到历史/版本页。",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = versionLabel,
                onValueChange = { versionLabel = it },
                label = { Text("版本号（例如 v2026.04.04-001）") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    val version = versionLabel.trim()
                    vm.recordPublishEntry(taskId, a.artifactId, a.name, version)
                    publishHint = "已记录发布申请：$version"
                },
                enabled = versionLabel.trim().isNotEmpty(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("提交发布申请")
            }
            publishHint?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PublishHistoryScreen(vm: AppViewModel, onBack: () -> Unit) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val sorted = state.publishHistory.sortedByDescending { it.createdAt }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("历史与版本") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { pad ->
        LazyColumn(
            modifier =
                Modifier
                    .padding(pad)
                    .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (sorted.isEmpty()) {
                item { Text("暂无记录。在产物详情页使用「提交发布申请」。") }
            } else {
                items(sorted, key = { it.id }) { e ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp)) {
                            Text("版本 ${e.versionLabel}", style = MaterialTheme.typography.titleSmall)
                            Text("任务 ${e.taskId}", style = MaterialTheme.typography.bodySmall)
                            Text("产物 ${e.artifactName ?: e.artifactId ?: "—"}")
                            Text("状态 ${e.status}", style = MaterialTheme.typography.bodySmall)
                            Text("时间 ${formatTimestamp(e.createdAt)}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}

private fun defaultVersionLabel(): String =
    "v" + SimpleDateFormat("yyyyMMdd-HHmmss", Locale.getDefault()).format(Date())

private fun formatTimestamp(millis: Long): String =
    runCatching {
        SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date(millis))
    }.getOrElse { millis.toString() }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProjectsTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val projects = if (state.dynamicProjects.isEmpty()) vm.mockProjects else state.dynamicProjects
    PullToRefreshBox(
        isRefreshing = state.isRefreshingProjects,
        onRefresh = { vm.refreshProjects() },
        modifier = Modifier.fillMaxSize(),
    ) {
        Column(Modifier.padding(20.dp).verticalScroll(rememberScrollState())) {
            Text("选择项目", style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.height(8.dp))
            Text(
                "projectId 须与控制面一致（默认 proj-1 与后端测试数据对齐）。",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(16.dp))
            projects.forEach { p ->
                val active = p.id == state.selectedProjectId
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .clickable { vm.selectProject(p.id) },
                ) {
                    RowWithProject(name = p.name, active = active)
                }
            }
        }
    }
}

@Composable
private fun RowWithProject(name: String, active: Boolean) {
    Column(Modifier.padding(16.dp)) {
        Text(name, style = MaterialTheme.typography.titleMedium)
        if (active) {
            Spacer(Modifier.height(4.dp))
            Text("当前", color = MaterialTheme.colorScheme.primary)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RowOfTargetChips(
    selected: String,
    onSelect: (String) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(
            selected = selected == GenerationTarget.WEB.name,
            onClick = { onSelect(GenerationTarget.WEB.name) },
            label = { Text(GenerationTarget.WEB.displayLabel()) },
        )
        FilterChip(
            selected = selected == GenerationTarget.WECHAT_MINI_PROGRAM.name,
            onClick = { onSelect(GenerationTarget.WECHAT_MINI_PROGRAM.name) },
            label = { Text(GenerationTarget.WECHAT_MINI_PROGRAM.displayLabel()) },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AccountTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var baseUrlDraft by rememberSaveable { mutableStateOf(state.baseUrl) }
    var targetDraft by rememberSaveable { mutableStateOf(state.generationTarget.name) }
    LaunchedEffect(state.baseUrl, state.generationTarget) {
        baseUrlDraft = state.baseUrl
        targetDraft = state.generationTarget.name
    }
    Column(Modifier.padding(20.dp)) {
        Text("我的", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        Text("连接与生成目标（PR-1）", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = baseUrlDraft,
            onValueChange = { baseUrlDraft = it },
            label = { Text("控制面 Base URL") },
            placeholder = { Text("留空=离线；模拟器访问本机可用 http://10.0.2.2:8080") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2,
        )
        Spacer(Modifier.height(12.dp))
        Text("生成目标（写入创建任务 assistant）", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        RowOfTargetChips(
            selected = targetDraft,
            onSelect = { targetDraft = it },
        )
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                val t =
                    when (targetDraft) {
                        GenerationTarget.WECHAT_MINI_PROGRAM.name -> GenerationTarget.WECHAT_MINI_PROGRAM
                        else -> GenerationTarget.WEB
                    }
                vm.saveConnectivitySettings(baseUrlDraft, t)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("保存连接设置")
        }
        Spacer(Modifier.height(24.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("显示名", style = MaterialTheme.typography.labelMedium)
                Text(state.session?.displayName ?: "—")
                Spacer(Modifier.height(12.dp))
                Text("Token（占位）", style = MaterialTheme.typography.labelMedium)
                Text(
                    state.session?.accessToken ?: "—",
                    fontFamily = FontFamily.Monospace,
                    maxLines = 1,
                )
            }
        }
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = { vm.logout() }) {
            Text("退出登录", color = MaterialTheme.colorScheme.error)
        }
    }
}
