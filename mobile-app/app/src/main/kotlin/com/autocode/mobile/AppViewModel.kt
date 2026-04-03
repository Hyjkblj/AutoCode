package com.autocode.mobile

import android.app.Application
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.autocode.mobile.network.ArtifactListItem
import com.autocode.mobile.network.ControlPlaneClient
import com.autocode.mobile.network.TaskSummaryDto
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlin.random.Random

private val Application.mobileDataStore by preferencesDataStore(name = "autocode_mobile")

private object PrefsKeys {
    val TOKEN = stringPreferencesKey("token")
    val DISPLAY = stringPreferencesKey("display")
    val PROJECT = stringPreferencesKey("project_id")
    val TASKS_JSON = stringPreferencesKey("tasks_json")
    val BASE_URL = stringPreferencesKey("base_url")
    val GENERATION_TARGET = stringPreferencesKey("generation_target")
    val PUBLISH_HISTORY_JSON = stringPreferencesKey("publish_history_json")
}

data class UiState(
    val isLoading: Boolean = true,
    val session: Session? = null,
    val selectedProjectId: String? = null,
    val tasks: List<TaskItem> = emptyList(),
    val errorMessage: String? = null,
    /** 控制面根 URL，空表示离线模拟（PR-1/PR-2） */
    val baseUrl: String = "",
    val generationTarget: GenerationTarget = GenerationTarget.WEB,
    /** PR-3：发布/版本历史（本地持久化） */
    val publishHistory: List<PublishHistoryEntry> = emptyList(),
)

class AppViewModel(application: Application) : AndroidViewModel(application) {

    private val previewMaxChars = 24_000

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    private val taskListSerializer = ListSerializer(TaskItem.serializer())
    private val publishHistorySerializer = ListSerializer(PublishHistoryEntry.serializer())

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    /** 与集成测试常用 projectId 对齐，便于真机连本地控制面。 */
    val mockProjects: List<Project> = listOf(
        Project("proj-1", "默认项目（proj-1）"),
        Project("proj-2", "备用项目（proj-2）"),
        Project("proj-3", "备用项目（proj-3）"),
    )

    init {
        viewModelScope.launch {
            loadFromStore()
            _uiState.update { it.copy(isLoading = false) }
            startLocalProgressTicker()
            startRemotePolling()
        }
    }

    private suspend fun loadFromStore() {
        val prefs = getApplication<Application>().mobileDataStore.data.first()
        val token = prefs[PrefsKeys.TOKEN].orEmpty()
        val display = prefs[PrefsKeys.DISPLAY].orEmpty()
        val projectId = prefs[PrefsKeys.PROJECT]
        val rawTasks = prefs[PrefsKeys.TASKS_JSON]
        val baseUrl = prefs[PrefsKeys.BASE_URL].orEmpty()
        val targetRaw = prefs[PrefsKeys.GENERATION_TARGET]
        val generationTarget =
            when (targetRaw?.trim()) {
                "wechat_mini" -> GenerationTarget.WECHAT_MINI_PROGRAM
                else -> GenerationTarget.WEB
            }

        val tasks: List<TaskItem> =
            if (rawTasks.isNullOrBlank()) emptyList()
            else runCatching { json.decodeFromString(taskListSerializer, rawTasks) }.getOrDefault(emptyList())

        val rawHistory = prefs[PrefsKeys.PUBLISH_HISTORY_JSON]
        val publishHistory: List<PublishHistoryEntry> =
            if (rawHistory.isNullOrBlank()) emptyList()
            else runCatching { json.decodeFromString(publishHistorySerializer, rawHistory) }.getOrDefault(emptyList())

        val session =
            if (token.isNotBlank() && display.isNotBlank()) Session(accessToken = token, displayName = display)
            else null

        val effectiveProject = projectId ?: mockProjects.first().id
        val normalizedTasks = tasks.map { t ->
            if (t.source == TaskSource.LOCAL && t.status == TaskStatus.QUEUED) {
                t.copy(
                    status = TaskStatus.RUNNING,
                    progress = maxOf(5, t.progress),
                    logs = t.logs + "应用重启后继续执行（仅本地任务）",
                    updatedAt = System.currentTimeMillis(),
                )
            } else {
                t
            }
        }

        _uiState.update {
            it.copy(
                session = session,
                selectedProjectId = if (session != null) effectiveProject else null,
                tasks = normalizedTasks,
                baseUrl = baseUrl,
                generationTarget = generationTarget,
                publishHistory = publishHistory,
            )
        }
        if (session != null && normalizedTasks != tasks) {
            persistTasks(normalizedTasks)
        }
    }

    private suspend fun persistAll() {
        val s = _uiState.value
        getApplication<Application>().mobileDataStore.edit { p ->
            val sess = s.session
            if (sess != null) {
                p[PrefsKeys.TOKEN] = sess.accessToken
                p[PrefsKeys.DISPLAY] = sess.displayName
            } else {
                p.remove(PrefsKeys.TOKEN)
                p.remove(PrefsKeys.DISPLAY)
            }
            val pid = s.selectedProjectId
            if (pid != null) p[PrefsKeys.PROJECT] = pid else p.remove(PrefsKeys.PROJECT)
            p[PrefsKeys.TASKS_JSON] = json.encodeToString(taskListSerializer, s.tasks)
            p[PrefsKeys.BASE_URL] = s.baseUrl.trim()
            p[PrefsKeys.GENERATION_TARGET] = generationTargetStorageValue(s.generationTarget)
            p[PrefsKeys.PUBLISH_HISTORY_JSON] = json.encodeToString(publishHistorySerializer, s.publishHistory)
        }
    }

    private fun generationTargetStorageValue(t: GenerationTarget): String =
        when (t) {
            GenerationTarget.WEB -> "web"
            GenerationTarget.WECHAT_MINI_PROGRAM -> "wechat_mini"
        }

    private suspend fun persistTasks(tasks: List<TaskItem>) {
        getApplication<Application>().mobileDataStore.edit { p ->
            p[PrefsKeys.TASKS_JSON] = json.encodeToString(taskListSerializer, tasks)
        }
    }

    fun consumeError() {
        _uiState.update { it.copy(errorMessage = null) }
    }

    fun saveConnectivitySettings(baseUrl: String, target: GenerationTarget) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    baseUrl = baseUrl.trim(),
                    generationTarget = target,
                    errorMessage = null,
                )
            }
            persistAll()
        }
    }

    fun login(username: String, password: String) {
        val u = username.trim()
        val p = password.trim()
        if (u.isEmpty() || p.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "请输入用户名和密码") }
            return
        }
        viewModelScope.launch {
            val base = _uiState.value.baseUrl.trim()
            if (base.isNotEmpty()) {
                val r = ControlPlaneClient.login(base, u, p)
                if (r.isSuccess) {
                    val token = r.getOrThrow()
                    val projectId = _uiState.value.selectedProjectId ?: mockProjects.first().id
                    _uiState.update {
                        it.copy(
                            session = Session(accessToken = token, displayName = u),
                            selectedProjectId = projectId,
                            errorMessage = null,
                        )
                    }
                    persistAll()
                } else {
                    val msg = r.exceptionOrNull()?.message ?: "登录失败"
                    _uiState.update { it.copy(errorMessage = msg) }
                }
            } else {
                val session = Session(accessToken = "mock.${System.currentTimeMillis()}", displayName = u)
                val projectId = _uiState.value.selectedProjectId ?: mockProjects.first().id
                _uiState.update {
                    it.copy(session = session, selectedProjectId = projectId, errorMessage = null)
                }
                persistAll()
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            val baseUrl = _uiState.value.baseUrl
            val target = _uiState.value.generationTarget
            _uiState.update {
                UiState(
                    isLoading = false,
                    session = null,
                    selectedProjectId = null,
                    tasks = emptyList(),
                    baseUrl = baseUrl,
                    generationTarget = target,
                    publishHistory = emptyList(),
                )
            }
            getApplication<Application>().mobileDataStore.edit { p ->
                p.remove(PrefsKeys.TOKEN)
                p.remove(PrefsKeys.DISPLAY)
                p.remove(PrefsKeys.PROJECT)
                p.remove(PrefsKeys.TASKS_JSON)
                p.remove(PrefsKeys.PUBLISH_HISTORY_JSON)
            }
        }
    }

    fun selectProject(projectId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(selectedProjectId = projectId) }
            persistAll()
        }
    }

    /**
     * PR-2：有控制面 URL 时走 HTTP 创建并轮询；否则本地模拟。
     */
    suspend fun createTaskAsync(prompt: String): String? {
        val projectId = _uiState.value.selectedProjectId ?: return null
        val text = prompt.trim()
        if (text.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "请输入任务描述") }
            return null
        }

        val base = _uiState.value.baseUrl.trim()
        val session = _uiState.value.session

        if (base.isNotEmpty() && session == null) {
            _uiState.update { it.copy(errorMessage = "已填写控制面地址，请先登录") }
            return null
        }

        if (base.isNotEmpty() && session != null) {
            val assistant = _uiState.value.generationTarget.assistantForApi()
            val r = ControlPlaneClient.createTask(base, session.accessToken, projectId, text, assistant)
            if (r.isSuccess) {
                val dto = r.getOrThrow()
                val mapped = mapServerToTaskItem(dto, projectId, text)
                _uiState.update { st -> st.copy(tasks = listOf(mapped) + st.tasks, errorMessage = null) }
                persistAll()
                return dto.taskId
            } else {
                val msg = r.exceptionOrNull()?.message ?: "创建任务失败"
                _uiState.update { it.copy(errorMessage = msg) }
                return null
            }
        }

        return createLocalTask(projectId, text)
    }

    private suspend fun createLocalTask(projectId: String, text: String): String {
        val id = "t_${System.currentTimeMillis()}_${Random.nextInt(1_000_000)}"
        val now = System.currentTimeMillis()
        val item =
            TaskItem(
                id = id,
                projectId = projectId,
                prompt = text,
                status = TaskStatus.QUEUED,
                progress = 0,
                logs = listOf("已加入队列（本地模拟）"),
                createdAt = now,
                updatedAt = now,
                source = TaskSource.LOCAL,
            )
        _uiState.update { st -> st.copy(tasks = listOf(item) + st.tasks, errorMessage = null) }
        persistAll()
        delay(450)
        _uiState.update { st ->
            st.copy(
                tasks =
                    st.tasks.map { t ->
                        if (t.id == id && t.status == TaskStatus.QUEUED) {
                            t.copy(
                                status = TaskStatus.RUNNING,
                                progress = 5,
                                logs = t.logs + "开始执行…",
                                updatedAt = System.currentTimeMillis(),
                            )
                        } else {
                            t
                        }
                    },
            )
        }
        persistAll()
        return id
    }

    private fun mapServerToTaskItem(dto: TaskSummaryDto, projectId: String, fallbackPrompt: String): TaskItem {
        val now = System.currentTimeMillis()
        val (st, prog) = mapServerStatus(dto.status)
        return TaskItem(
            id = dto.taskId,
            projectId = dto.projectId ?: projectId,
            prompt = dto.prompt ?: fallbackPrompt,
            status = st,
            progress = prog,
            logs = listOf("已在控制面创建任务", "状态: ${dto.status}"),
            createdAt = now,
            updatedAt = now,
            source = TaskSource.REMOTE,
        )
    }

    private fun mapServerStatus(status: String): Pair<TaskStatus, Int> =
        when (status.uppercase()) {
            "QUEUED" -> TaskStatus.QUEUED to 12
            "RUNNING" -> TaskStatus.RUNNING to 55
            "WAITING_APPROVAL", "PAUSED" -> TaskStatus.RUNNING to 78
            "DONE" -> TaskStatus.SUCCEEDED to 100
            "FAILED", "CANCELED" -> TaskStatus.FAILED to 100
            else -> TaskStatus.RUNNING to 40
        }

    fun taskById(id: String): TaskItem? = _uiState.value.tasks.find { it.id == id }

    fun tasksForCurrentProject(): List<TaskItem> {
        val pid = _uiState.value.selectedProjectId ?: return emptyList()
        return _uiState.value.tasks.filter { it.projectId == pid }.sortedByDescending { it.createdAt }
    }

    fun succeededTasksForCurrentProject(): List<TaskItem> =
        tasksForCurrentProject().filter { it.status == TaskStatus.SUCCEEDED }

    /**
     * PR-3：拉取任务下已上传产物；离线且任务已完成时返回占位条目。
     */
    suspend fun loadArtifactsForTask(taskId: String): Result<List<ArtifactListItem>> {
        val base = _uiState.value.baseUrl.trim()
        val session = _uiState.value.session
        if (base.isNotEmpty() && session != null) {
            return ControlPlaneClient.listArtifacts(base, session.accessToken, taskId)
        }
        val task = taskById(taskId)
        if (task != null && task.status == TaskStatus.SUCCEEDED) {
            return Result.success(
                listOf(
                    ArtifactListItem(
                        artifactId = "local-mock-1",
                        taskId = taskId,
                        name = "产物占位.zip",
                        contentType = "application/zip",
                        sizeBytes = 2048L,
                        sha256 = "mock-sha256",
                    ),
                ),
            )
        }
        return Result.success(emptyList())
    }

    suspend fun loadArtifactPreview(taskId: String, artifact: ArtifactListItem): Result<ArtifactPreview> {
        val title = artifact.name ?: artifact.artifactId
        val base = _uiState.value.baseUrl.trim()
        val session = _uiState.value.session

        if (base.isEmpty()) {
            return Result.success(
                ArtifactPreview(
                    title = title,
                    contentType = artifact.contentType,
                    content =
                        buildString {
                            appendLine("离线模式预览（Mock）")
                            appendLine("taskId=$taskId")
                            appendLine("artifactId=${artifact.artifactId}")
                            appendLine("name=${artifact.name ?: "unknown"}")
                            appendLine("提示：连接控制面后可读取真实产物内容。")
                        },
                    truncated = false,
                    byteSize = (artifact.sizeBytes ?: 0L).coerceAtMost(Int.MAX_VALUE.toLong()).toInt(),
                ),
            )
        }

        if (session == null) {
            return Result.failure(IllegalStateException("请先登录后再加载产物预览"))
        }

        if (!isTextPreviewable(artifact.contentType, artifact.name)) {
            return Result.failure(IllegalStateException("该产物是二进制文件，当前仅支持文本预览"))
        }

        return ControlPlaneClient
            .downloadArtifact(base, session.accessToken, taskId, artifact.artifactId)
            .mapCatching { d ->
                val raw = d.bytes.toString(Charsets.UTF_8)
                val truncated = raw.length > previewMaxChars
                ArtifactPreview(
                    title = artifact.name ?: d.fileName ?: artifact.artifactId,
                    contentType = artifact.contentType ?: d.contentType,
                    content = if (truncated) raw.take(previewMaxChars) else raw,
                    truncated = truncated,
                    byteSize = d.bytes.size,
                )
            }
    }

    private fun isTextPreviewable(contentType: String?, fileName: String?): Boolean {
        val ct = contentType?.lowercase().orEmpty()
        if (ct.startsWith("text/")) return true
        if (
            ct.contains("json") ||
            ct.contains("xml") ||
            ct.contains("yaml") ||
            ct.contains("x-www-form-urlencoded") ||
            ct.contains("javascript")
        ) {
            return true
        }
        val name = fileName?.lowercase().orEmpty()
        val suffixes =
            listOf(
                ".txt", ".md", ".json", ".xml", ".yaml", ".yml",
                ".js", ".ts", ".tsx", ".jsx", ".html", ".css",
                ".kt", ".kts", ".java", ".gradle", ".properties", ".sql",
            )
        return suffixes.any { s -> name.endsWith(s) }
    }

    fun recordPublishEntry(
        taskId: String,
        artifactId: String?,
        artifactName: String?,
        versionLabel: String,
        status: String = "submitted_mock",
    ) {
        viewModelScope.launch {
            val normalizedVersion = versionLabel.trim().ifEmpty { "v-${System.currentTimeMillis()}" }
            val e =
                PublishHistoryEntry(
                    id = "pub_${System.currentTimeMillis()}",
                    taskId = taskId,
                    artifactId = artifactId,
                    artifactName = artifactName,
                    versionLabel = normalizedVersion,
                    status = status,
                    createdAt = System.currentTimeMillis(),
                )
            _uiState.update { it.copy(publishHistory = listOf(e) + it.publishHistory) }
            persistAll()
        }
    }

    private fun startLocalProgressTicker() {
        viewModelScope.launch {
            while (isActive) {
                delay(1200)
                val before = _uiState.value.tasks
                val after =
                    before.map { t ->
                        if (t.source != TaskSource.LOCAL) return@map t
                        if (t.status != TaskStatus.RUNNING) return@map t
                        val delta = 8 + Random.nextInt(10)
                        val np = (t.progress + delta).coerceAtMost(100)
                        val logs = t.logs.toMutableList()
                        if (np >= 28 && t.progress < 28) logs += "分析需求…"
                        if (np >= 55 && t.progress < 55) logs += "生成代码与资源（本地模拟）…"
                        if (np >= 100 && t.progress < 100) {
                            logs += "完成（本地模拟）"
                        }
                        val ns = if (np >= 100) TaskStatus.SUCCEEDED else TaskStatus.RUNNING
                        t.copy(status = ns, progress = np, logs = logs, updatedAt = System.currentTimeMillis())
                    }
                if (after != before) {
                    _uiState.update { it.copy(tasks = after) }
                    persistTasks(after)
                }
            }
        }
    }

    private fun startRemotePolling() {
        viewModelScope.launch {
            while (isActive) {
                delay(2500)
                val st = _uiState.value
                val base = st.baseUrl.trim()
                val sess = st.session ?: continue
                if (base.isEmpty()) continue
                val remote = st.tasks.filter { it.source == TaskSource.REMOTE }
                if (remote.isEmpty()) continue
                for (t in remote) {
                    val r = ControlPlaneClient.getTask(base, sess.accessToken, t.id)
                    if (r.isSuccess) {
                        mergeRemoteTask(r.getOrThrow())
                    }
                }
            }
        }
    }

    private suspend fun mergeRemoteTask(dto: TaskSummaryDto) {
        val (st, prog) = mapServerStatus(dto.status)
        _uiState.update { state ->
            val next =
                state.tasks.map { t ->
                    if (t.id != dto.taskId) return@map t
                    val statusLine = "控制面: ${dto.status}"
                    val newLogs =
                        if (t.logs.lastOrNull() == statusLine) {
                            t.logs
                        } else {
                            (t.logs + statusLine).takeLast(40)
                        }
                    t.copy(
                        status = st,
                        progress = prog,
                        prompt = dto.prompt ?: t.prompt,
                        logs = newLogs,
                        updatedAt = System.currentTimeMillis(),
                    )
                }
            state.copy(tasks = next)
        }
        persistTasks(_uiState.value.tasks)
    }
}

object AppViewModelFactory {
    fun create(application: Application): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                if (modelClass.isAssignableFrom(AppViewModel::class.java)) {
                    return AppViewModel(application) as T
                }
                throw IllegalArgumentException("Unknown ViewModel: ${modelClass.name}")
            }
        }
}
