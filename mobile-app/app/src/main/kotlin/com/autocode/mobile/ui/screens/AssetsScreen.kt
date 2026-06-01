package com.autocode.mobile.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.ArtifactPreview
import com.autocode.mobile.network.ArtifactListItem
import com.autocode.mobile.ui.components.MobileUiTestTags
import com.autocode.mobile.ui.components.defaultVersionLabel
import com.autocode.mobile.ui.components.environmentDisplayLabel
import com.autocode.mobile.ui.components.formatTimestamp
import com.autocode.mobile.ui.components.normalizeEnvironmentForApi
import com.autocode.mobile.ui.components.publishStatusLabel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ArtifactsHubTab(vm: AppViewModel, nav: NavHostController) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val done = vm.succeededTasksForCurrentProject()
    LaunchedEffect(state.selectedProjectId, state.baseUrl, state.session?.accessToken) {
        vm.refreshTasks()
    }
    Column(Modifier.padding(16.dp)) {
        TopAppBar(
            title = { Text("产物") },
            actions = {
                IconButton(
                    onClick = { vm.refreshTasks() },
                    enabled = !state.isRefreshingTasks,
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = "刷新任务")
                }
            },
        )
        if (state.isRefreshingTasks) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
        }
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
internal fun ArtifactsForTaskScreen(
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
            Text("任务编号：$taskId", style = MaterialTheme.typography.bodySmall)
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
internal fun ArtifactDetailScreen(
    vm: AppViewModel,
    taskId: String,
    artifactId: String,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var loading by remember { mutableStateOf(true) }
    var art by remember { mutableStateOf<ArtifactListItem?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    var preview by remember { mutableStateOf<ArtifactPreview?>(null) }
    var previewErr by remember { mutableStateOf<String?>(null) }
    var previewLoading by remember { mutableStateOf(false) }
    var accessUrl by remember { mutableStateOf<com.autocode.mobile.ArtifactAccessUrl?>(null) }
    var accessUrlErr by remember { mutableStateOf<String?>(null) }
    var accessUrlLoading by remember { mutableStateOf(false) }
    var versionLabel by rememberSaveable(taskId, artifactId) { mutableStateOf(defaultVersionLabel()) }
    var environment by rememberSaveable(taskId, artifactId) { mutableStateOf("测试环境") }
    var publishSubmitting by remember { mutableStateOf(false) }
    var publishError by remember { mutableStateOf<String?>(null) }
    var publishHint by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(taskId, artifactId) {
        loading = true
        err = null
        art = null
        preview = null
        previewErr = null
        previewLoading = false
        accessUrl = null
        accessUrlErr = null
        accessUrlLoading = false
        versionLabel = defaultVersionLabel()
        environment = "测试环境"
        publishSubmitting = false
        publishError = null
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
            Text("产物编号：${a.artifactId}")
            Text("内容类型：${a.contentType ?: "—"}")
            Text("文件大小：${a.sizeBytes ?: "—"} 字节")
            Text("摘要 SHA-256：${a.sha256 ?: "—"}", fontFamily = FontFamily.Monospace)
            Spacer(Modifier.height(20.dp))
            Text(
                "在线访问入口：将产物托管到服务器并生成可访问链接。",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    scope.launch {
                        accessUrlLoading = true
                        accessUrlErr = null
                        accessUrl = null
                        vm.resolveArtifactAccessUrl(taskId, a).fold(
                            onSuccess = { accessUrl = it },
                            onFailure = { accessUrlErr = it.message ?: "生成访问链接失败" },
                        )
                        accessUrlLoading = false
                    }
                },
                enabled = !accessUrlLoading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (accessUrlLoading) "生成中..." else "生成访问链接")
            }
            accessUrlErr?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            accessUrl?.let { link ->
                Spacer(Modifier.height(10.dp))
                Text("访问链接（点击后打开浏览器）：", style = MaterialTheme.typography.bodySmall)
                Text(
                    text = link.url,
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    color = MaterialTheme.colorScheme.primary,
                    textDecoration = TextDecoration.Underline,
                    modifier = Modifier.clickable {
                        runCatching {
                            val browserIntent =
                                Intent(Intent.ACTION_VIEW, Uri.parse(link.url)).apply {
                                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                }
                            context.startActivity(browserIntent)
                        }.onFailure { e ->
                            accessUrlErr = e.message ?: "无法打开浏览器"
                        }
                    },
                )
                link.shortUrl
                    ?.takeIf { it.isNotBlank() && it != link.url }
                    ?.let { short ->
                        Spacer(Modifier.height(6.dp))
                        Text("短链地址（点击后打开浏览器）：", style = MaterialTheme.typography.bodySmall)
                        Text(
                            text = short,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            color = MaterialTheme.colorScheme.primary,
                            textDecoration = TextDecoration.Underline,
                            modifier = Modifier.clickable {
                                runCatching {
                                    val browserIntent =
                                        Intent(Intent.ACTION_VIEW, Uri.parse(short)).apply {
                                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                        }
                                    context.startActivity(browserIntent)
                                }.onFailure { e ->
                                    accessUrlErr = e.message ?: "无法打开浏览器"
                                }
                            },
                        )
                    }
                link.shareUrl
                    ?.takeIf { it.isNotBlank() && it != link.url && it != link.shortUrl }
                    ?.let { share ->
                        Spacer(Modifier.height(6.dp))
                        Text("备用分享链接：", style = MaterialTheme.typography.bodySmall)
                        Text(
                            text = share,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            color = MaterialTheme.colorScheme.primary,
                            textDecoration = TextDecoration.Underline,
                            modifier = Modifier.clickable {
                                runCatching {
                                    val browserIntent =
                                        Intent(Intent.ACTION_VIEW, Uri.parse(share)).apply {
                                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                        }
                                    context.startActivity(browserIntent)
                                }.onFailure { e ->
                                    accessUrlErr = e.message ?: "无法打开浏览器"
                                }
                            },
                        )
                    }
            }
            Spacer(Modifier.height(12.dp))
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
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .testTag(MobileUiTestTags.ARTIFACT_PREVIEW_LOAD_BUTTON),
            ) {
                Text(if (previewLoading) "加载预览中..." else "加载预览")
            }
            previewErr?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            preview?.let { p ->
                Spacer(Modifier.height(12.dp))
                ArtifactPreviewCard(preview = p)
            }
            Spacer(Modifier.height(12.dp))
            Text(
                "发布入口：填写版本号并提交到控制面 deploy API。",
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
            OutlinedTextField(
                value = environment,
                onValueChange = { environment = it },
                label = { Text("发布环境（默认测试环境）") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    scope.launch {
                        val version = versionLabel.trim()
                        if (version.isEmpty()) return@launch
                        publishSubmitting = true
                        publishError = null
                        publishHint = null
                        vm.recordPublishEntry(
                            taskId = taskId,
                            artifactId = a.artifactId,
                            artifactName = a.name,
                            versionLabel = version,
                            environment = normalizeEnvironmentForApi(environment),
                        ).fold(
                            onSuccess = { entry ->
                                publishHint = "发布任务已提交：${entry.taskId}（${entry.status}）"
                                versionLabel = defaultVersionLabel()
                                vm.subscribeTaskEvents(entry.taskId)
                            },
                            onFailure = { ex ->
                                publishError = ex.message ?: "提交发布请求失败"
                            },
                        )
                        publishSubmitting = false
                    }
                },
                enabled = versionLabel.trim().isNotEmpty() && !publishSubmitting,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (publishSubmitting) "提交中..." else "提交发布请求")
            }
            publishError?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            publishHint?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@Composable
internal fun ArtifactPreviewCard(preview: ArtifactPreview) {
    Card(
        modifier =
            Modifier
                .fillMaxWidth()
                .testTag(MobileUiTestTags.ARTIFACT_PREVIEW_CARD),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(preview.title, style = MaterialTheme.typography.titleSmall)
            Text(
                "${preview.contentType ?: "text/plain"} · ${preview.byteSize} 字节",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(8.dp))
            Text(preview.content, fontFamily = FontFamily.Monospace)
            if (preview.truncated) {
                Spacer(Modifier.height(8.dp))
                Text("预览内容已截断，请下载完整文件查看。", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PublishHistoryScreen(vm: AppViewModel, onBack: () -> Unit) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val sorted = state.publishHistory.sortedByDescending { it.createdAt }
    LaunchedEffect(state.baseUrl, state.session?.accessToken) {
        vm.refreshPublishHistory()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("发布历史") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(
                        onClick = { vm.refreshPublishHistory() },
                        enabled = !state.isRefreshingPublishHistory,
                    ) {
                        Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
    ) { pad ->
        PullToRefreshBox(
            isRefreshing = state.isRefreshingPublishHistory,
            onRefresh = { vm.refreshPublishHistory() },
            modifier =
                Modifier
                    .padding(pad)
                    .fillMaxSize(),
        ) {
            LazyColumn(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (sorted.isEmpty()) {
                    item { Text("暂无发布记录，可在产物详情页发起发布。") }
                } else {
                    items(sorted, key = { it.id }) { entry ->
                        DeployStatusCard(entry)
                    }
                }
            }
        }
    }
}

@Composable
private fun DeployStatusCard(entry: com.autocode.mobile.PublishHistoryEntry) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text("版本 ${entry.versionLabel}", style = MaterialTheme.typography.titleSmall)
            Text("发布任务 ${entry.taskId}", style = MaterialTheme.typography.bodySmall)
            entry.sourceTaskId?.takeIf { it.isNotBlank() }?.let {
                Text("来源任务 $it", style = MaterialTheme.typography.bodySmall)
            }
            Text("产物 ${entry.artifactName ?: entry.artifactId ?: "-"}")
            entry.environment?.takeIf { it.isNotBlank() }?.let {
                Text("环境 ${environmentDisplayLabel(it)}", style = MaterialTheme.typography.bodySmall)
            }
            Text("状态：${publishStatusLabel(entry.status)}", style = MaterialTheme.typography.bodySmall)
            entry.endpointUrl?.takeIf { it.isNotBlank() }?.let {
                Text(
                    text = "访问地址 $it",
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                )
            }
            entry.deployRequestId?.takeIf { it.isNotBlank() }?.let {
                Text("请求编号 $it", style = MaterialTheme.typography.bodySmall)
            }
            Text("时间 ${formatTimestamp(entry.createdAt)}", style = MaterialTheme.typography.bodySmall)
        }
    }
}
