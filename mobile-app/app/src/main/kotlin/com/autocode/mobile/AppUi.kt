package com.autocode.mobile

import android.app.Application
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
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

private sealed class Tab(
    val route: String,
    val label: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
) {
    data object Home : Tab("home", "首页", Icons.Filled.Home)
    data object Tasks : Tab("tasks", "任务", Icons.Filled.List)
    data object Projects : Tab("projects", "项目", Icons.Filled.Folder)
    data object Account : Tab("account", "我的", Icons.Filled.Person)
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
    val showBar = current in listOf(Tab.Home.route, Tab.Tasks.route, Tab.Projects.route, Tab.Account.route)

    Scaffold(
        bottomBar = {
            if (showBar) {
                NavigationBar {
                    val tabs = listOf(Tab.Home, Tab.Tasks, Tab.Projects, Tab.Account)
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
                TaskDetailTab(vm, taskId = id, onBack = { innerNav.popBackStack() })
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
    val project = vm.mockProjects.find { it.id == state.selectedProjectId }
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
                    "PR-1：登录、会话、项目、生成目标（Web/微信小程序）。\n" +
                        "PR-2：自然语言创建任务；配置控制面后通过 HTTP 轮询任务状态，否则本地进度模拟。",
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskListTab(vm: AppViewModel, nav: NavHostController) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    var prompt by rememberSaveable { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val list = vm.tasksForCurrentProject()
    val project = vm.mockProjects.find { it.id == state.selectedProjectId }

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
        OutlinedTextField(
            value = prompt,
            onValueChange = { prompt = it },
            label = { Text("自然语言描述") },
            modifier = Modifier
                .fillMaxWidth()
                .height(140.dp),
            minLines = 4,
        )
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskDetailTab(vm: AppViewModel, taskId: String, onBack: () -> Unit) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val task = state.tasks.find { it.id == taskId }

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
                if (task.source == TaskSource.REMOTE) "日志（控制面轮询）" else "日志（本地模拟）",
                style = MaterialTheme.typography.titleSmall,
            )
            Spacer(Modifier.height(8.dp))
            task.logs.forEach { line ->
                Text("· $line", fontFamily = FontFamily.Monospace)
            }
        }
    }
}

@Composable
private fun ProjectsTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    Column(Modifier.padding(20.dp)) {
        Text("选择项目", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))
        Text(
            "projectId 须与控制面一致（默认 proj-1 与后端测试数据对齐）。",
            style = MaterialTheme.typography.bodySmall,
        )
        Spacer(Modifier.height(16.dp))
        vm.mockProjects.forEach { p ->
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
