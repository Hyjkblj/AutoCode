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
import com.autocode.mobile.network.TaskEventDto
import com.autocode.mobile.network.TaskSummaryDto
import com.autocode.mobile.network.WebSocketClient
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
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.longOrNull
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
    val dynamicProjects: List<Project> = emptyList(),
    val isRefreshingProjects: Boolean = false,
    val tasks: List<TaskItem> = emptyList(),
    val taskEvents: Map<String, List<TaskEventDto>> = emptyMap(),
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
    private val _pendingApproval = MutableStateFlow<ApprovalRequest?>(null)
    val pendingApproval: StateFlow<ApprovalRequest?> = _pendingApproval.asStateFlow()
    private val wsClient = WebSocketClient()
    private var subscribedTaskId: String? = null
    private var subscribedBaseUrl: String? = null
    private var subscribedToken: String? = null
    private val maxTaskEventsPerTask = 300
    private val fallbackProjectMap: Map<String, Project> by lazy {
        mockProjects.associateBy { it.id }
    }

    /** 与集成测试常用 projectId 对齐，便于真机连本地控制面。 */
    val mockProjects: List<Project> = listOf(
        Project("proj-1", "默认项目（proj-1）"),
        Project("proj-2", "备用项目（proj-2）"),
        Project("proj-3", "备用项目（proj-3）"),
    )

    init {
        viewModelScope.launch {
            loadFromStore()
            refreshProjectsInternal()
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

        val initialProjects = deriveProjectsFromTasks(tasks = tasks, selectedProjectId = projectId)
        val effectiveProject =
            when {
                session == null -> null
                !projectId.isNullOrBlank() -> projectId
                else -> initialProjects.firstOrNull()?.id ?: mockProjects.first().id
            }
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
                selectedProjectId = effectiveProject,
                dynamicProjects = initialProjects,
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
            refreshProjectsInternal()
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
                    refreshProjectsInternal()
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
                refreshProjectsInternal()
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            unsubscribeTaskEvents()
            _pendingApproval.value = null
            val baseUrl = _uiState.value.baseUrl
            val target = _uiState.value.generationTarget
            _uiState.update {
                UiState(
                    isLoading = false,
                    session = null,
                    selectedProjectId = null,
                    dynamicProjects = mockProjects,
                    isRefreshingProjects = false,
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

    fun refreshProjects() {
        viewModelScope.launch {
            refreshProjectsInternal()
        }
    }

    private suspend fun refreshProjectsInternal() {
        val before = _uiState.value
        _uiState.update { it.copy(isRefreshingProjects = true) }
        val projects = deriveProjectsFromTasks(before.tasks, before.selectedProjectId)
        val selected =
            when {
                before.session == null -> null
                !before.selectedProjectId.isNullOrBlank() && projects.any { it.id == before.selectedProjectId } ->
                    before.selectedProjectId
                else -> projects.firstOrNull()?.id
            }
        _uiState.update {
            it.copy(
                dynamicProjects = projects,
                selectedProjectId = selected,
                isRefreshingProjects = false,
            )
        }
        persistAll()
    }

    private fun deriveProjectsFromTasks(tasks: List<TaskItem>, selectedProjectId: String?): List<Project> {
        val ids = LinkedHashSet<String>()
        selectedProjectId?.trim()?.takeIf { it.isNotEmpty() }?.let { ids += it }
        tasks
            .asSequence()
            .map { it.projectId.trim() }
            .filter { it.isNotEmpty() }
            .forEach { ids += it }
        if (ids.isEmpty()) {
            mockProjects.forEach { ids += it.id }
        }
        return ids.map { projectFromId(it) }
    }

    private fun projectFromId(projectId: String): Project =
        fallbackProjectMap[projectId] ?: Project(projectId, "项目 $projectId")

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
                refreshProjectsInternal()
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

    fun subscribeTaskEvents(taskId: String) {
        val normalizedTaskId = taskId.trim()
        if (normalizedTaskId.isEmpty()) return

        val state = _uiState.value
        val base = state.baseUrl.trim()
        val token = state.session?.accessToken?.trim().orEmpty()
        if (base.isEmpty() || token.isEmpty()) {
            unsubscribeTaskEvents(normalizedTaskId)
            return
        }

        val alreadySubscribed =
            subscribedTaskId == normalizedTaskId &&
                subscribedBaseUrl == base &&
                subscribedToken == token
        if (alreadySubscribed) return

        unsubscribeTaskEvents()
        subscribedTaskId = normalizedTaskId
        subscribedBaseUrl = base
        subscribedToken = token

        viewModelScope.launch {
            backfillTaskEvents(normalizedTaskId, lastSeq(normalizedTaskId))
            wsClient.connect(
                baseUrl = base,
                bearerToken = token,
                taskId = normalizedTaskId,
                lastSeq = lastSeq(normalizedTaskId),
                onEvent = { event ->
                    if (subscribedTaskId == normalizedTaskId) {
                        viewModelScope.launch {
                            mergeTaskEvents(normalizedTaskId, listOf(event))
                        }
                    }
                },
                onDisconnect = {
                    if (subscribedTaskId == normalizedTaskId) {
                        viewModelScope.launch {
                            backfillTaskEvents(normalizedTaskId, lastSeq(normalizedTaskId))
                        }
                    }
                },
            )
        }
    }

    fun unsubscribeTaskEvents(taskId: String? = null) {
        val current = subscribedTaskId ?: return
        if (taskId != null && taskId != current) return
        wsClient.disconnect()
        subscribedTaskId = null
        subscribedBaseUrl = null
        subscribedToken = null
    }

    fun submitApproval(
        taskId: String,
        approvalId: String,
        decision: String,
        comment: String? = null,
    ) {
        val normalizedTaskId = taskId.trim()
        val normalizedApprovalId = approvalId.trim()
        val normalizedDecision =
            when (decision.trim().lowercase()) {
                "approve", "approved" -> "approve"
                "reject", "rejected", "deny", "denied" -> "reject"
                else -> ""
            }
        if (normalizedTaskId.isEmpty() || normalizedApprovalId.isEmpty() || normalizedDecision.isEmpty()) {
            _uiState.update { it.copy(errorMessage = "审批参数无效") }
            return
        }
        viewModelScope.launch {
            val state = _uiState.value
            val base = state.baseUrl.trim()
            val token = state.session?.accessToken?.trim().orEmpty()
            if (base.isEmpty() || token.isEmpty()) {
                _uiState.update { it.copy(errorMessage = "当前为离线模式，无法提交审批") }
                return@launch
            }
            val result =
                ControlPlaneClient.submitApproval(
                    baseUrl = base,
                    bearerToken = token,
                    taskId = normalizedTaskId,
                    approvalId = normalizedApprovalId,
                    decision = normalizedDecision,
                    comment = comment,
                )
            if (result.isSuccess) {
                _pendingApproval.update { pending ->
                    if (pending?.approvalId == normalizedApprovalId) null else pending
                }
                mergeRemoteTask(result.getOrThrow())
            } else {
                _uiState.update {
                    it.copy(errorMessage = result.exceptionOrNull()?.message ?: "审批提交失败")
                }
            }
        }
    }

    fun dismissPendingApproval(taskId: String? = null, approvalId: String? = null) {
        _pendingApproval.update { current ->
            if (current == null) return@update null
            if (taskId != null && current.taskId != taskId) return@update current
            if (approvalId != null && current.approvalId != approvalId) return@update current
            null
        }
    }

    fun eventLine(event: TaskEventDto): String {
        val payload = event.payload
        return when (event.type?.uppercase()) {
            "TASK_STARTED" -> "任务已开始"
            "ASSISTANT_OUTPUT" ->
                stringValue(payload, "message", "content", "text")
                    ?: "AI 输出"
            "TOOL_START" -> {
                val tool = stringValue(payload, "tool", "toolName") ?: "unknown"
                val cmd = stringValue(payload, "command", "cmd") ?: "-"
                "执行工具：$tool  命令：$cmd"
            }
            "TOOL_END" -> {
                val status = stringValue(payload, "status", "result") ?: "unknown"
                val execMs = longValue(payload, "execMs", "elapsedMs", "durationMs")
                if (execMs != null) {
                    "工具完成：$status  耗时：${execMs}ms"
                } else {
                    "工具完成：$status"
                }
            }
            "FILE_PATCH_PREVIEW" -> "代码变更预览"
            "APPROVAL_REQUIRED" -> "等待审批"
            "APPROVAL_RESULT" -> {
                val decision = stringValue(payload, "decision", "result") ?: "unknown"
                "审批结果：$decision"
            }
            "TASK_DONE" -> "任务完成"
            "TASK_FAILED" -> {
                val reason = stringValue(payload, "reason", "message", "error")
                if (reason.isNullOrBlank()) "任务失败" else "任务失败：$reason"
            }
            else -> event.type ?: "EVENT"
        }
    }

    private fun lastSeq(taskId: String): Long =
        _uiState.value.taskEvents[taskId].orEmpty().maxOfOrNull { it.seq } ?: 0L

    private suspend fun backfillTaskEvents(taskId: String, lastSeq: Long) {
        val state = _uiState.value
        val base = state.baseUrl.trim()
        val token = state.session?.accessToken?.trim().orEmpty()
        if (base.isEmpty() || token.isEmpty()) return
        val result = ControlPlaneClient.listTaskEvents(base, token, taskId, lastSeq)
        val events = result.getOrNull().orEmpty()
        if (events.isNotEmpty()) {
            mergeTaskEvents(taskId, events)
        }
    }

    private suspend fun mergeTaskEvents(taskId: String, incoming: List<TaskEventDto>) {
        if (incoming.isEmpty()) return
        val sortedIncoming = incoming.sortedBy { it.seq }
        _uiState.update { state ->
            val mergedEvents = mergeEventList(state.taskEvents[taskId].orEmpty(), sortedIncoming)
            val mergedTasks = sortedIncoming.fold(state.tasks) { acc, event ->
                applyEventToTasks(acc, taskId, event)
            }
            state.copy(
                taskEvents = state.taskEvents + (taskId to mergedEvents),
                tasks = mergedTasks,
            )
        }
        syncPendingApprovalFromEvents(taskId, sortedIncoming)
        persistTasks(_uiState.value.tasks)
    }

    private fun mergeEventList(existing: List<TaskEventDto>, incoming: List<TaskEventDto>): List<TaskEventDto> {
        val merged = LinkedHashMap<String, TaskEventDto>()
        (existing + incoming).sortedBy { it.seq }.forEach { event ->
            val key =
                when {
                    !event.eventId.isNullOrBlank() -> "id:${event.eventId}"
                    event.seq > 0L -> "seq:${event.seq}"
                    else -> "raw:${event.type}:${event.timestamp}:${event.payload}"
                }
            merged[key] = event
        }
        return merged.values.sortedBy { it.seq }.takeLast(maxTaskEventsPerTask)
    }

    private fun applyEventToTasks(tasks: List<TaskItem>, taskId: String, event: TaskEventDto): List<TaskItem> {
        val line = eventLine(event)
        val statusHint = eventStatusHint(event)
        val now = System.currentTimeMillis()
        return tasks.map { item ->
            if (item.id != taskId) return@map item
            val logs = if (item.logs.lastOrNull() == line) item.logs else (item.logs + line).takeLast(80)
            val nextStatus = statusHint?.first ?: item.status
            val nextProgress = statusHint?.second?.coerceAtLeast(item.progress) ?: item.progress
            item.copy(
                status = nextStatus,
                progress = nextProgress,
                logs = logs,
                updatedAt = now,
            )
        }
    }

    private fun eventStatusHint(event: TaskEventDto): Pair<TaskStatus, Int>? =
        when (event.type?.uppercase()) {
            "TASK_STARTED" -> TaskStatus.RUNNING to 15
            "APPROVAL_REQUIRED" -> TaskStatus.RUNNING to 78
            "TASK_DONE" -> TaskStatus.SUCCEEDED to 100
            "TASK_FAILED" -> TaskStatus.FAILED to 100
            else -> null
        }

    private fun syncPendingApprovalFromEvents(taskId: String, incoming: List<TaskEventDto>) {
        incoming.forEach { event ->
            when (event.type?.uppercase()) {
                "APPROVAL_REQUIRED" -> {
                    val request = toApprovalRequest(taskId, event) ?: return@forEach
                    _pendingApproval.value = request
                }
                "APPROVAL_RESULT", "TASK_DONE", "TASK_FAILED" -> {
                    dismissPendingApproval(taskId = taskId)
                }
            }
        }
    }

    private fun toApprovalRequest(taskId: String, event: TaskEventDto): ApprovalRequest? {
        val payload = event.payload
        val approvalId = stringValue(payload, "approvalId") ?: return null
        val timeout =
            longValue(payload, "approvalTimeoutSeconds", "timeoutSeconds")
                ?.coerceAtLeast(1L)
                ?.coerceAtMost(3600L)
                ?.toInt()
                ?: 120
        return ApprovalRequest(
            approvalId = approvalId,
            taskId = taskId,
            action = stringValue(payload, "action"),
            tool = stringValue(payload, "tool"),
            command = stringValue(payload, "command", "cmd"),
            cwd = stringValue(payload, "cwd"),
            riskScore = doubleValue(payload, "riskScore"),
            reason = stringValue(payload, "reason"),
            timeoutSeconds = timeout,
        )
    }

    private fun stringValue(payload: JsonObject, vararg keys: String): String? {
        for (key in keys) {
            val primitive = payload[key] as? JsonPrimitive ?: continue
            val raw = primitive.contentOrNull?.trim().orEmpty()
            if (raw.isNotEmpty()) return raw
        }
        return null
    }

    private fun doubleValue(payload: JsonObject, vararg keys: String): Double? {
        for (key in keys) {
            val primitive = payload[key] as? JsonPrimitive ?: continue
            primitive.doubleOrNull?.let { return it }
            primitive.longOrNull?.toDouble()?.let { return it }
            primitive.contentOrNull?.trim()?.toDoubleOrNull()?.let { return it }
        }
        return null
    }

    private fun longValue(payload: JsonObject, vararg keys: String): Long? {
        for (key in keys) {
            val primitive = payload[key] as? JsonPrimitive ?: continue
            primitive.longOrNull?.let { return it }
            primitive.doubleOrNull?.toLong()?.let { return it }
            primitive.contentOrNull?.trim()?.toLongOrNull()?.let { return it }
        }
        return null
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
                delay(3500)
                val st = _uiState.value
                val base = st.baseUrl.trim()
                val sess = st.session ?: continue
                if (base.isEmpty()) continue
                val activeSubscribedTask = subscribedTaskId
                val remote =
                    st.tasks.filter {
                        it.source == TaskSource.REMOTE &&
                            it.id != activeSubscribedTask
                    }
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
            val incomingProjectId = dto.projectId?.trim().orEmpty()
            val hasIncomingProject =
                incomingProjectId.isNotEmpty() &&
                    state.dynamicProjects.none { it.id == incomingProjectId }
            val mergedProjects =
                if (hasIncomingProject) {
                    state.dynamicProjects + projectFromId(incomingProjectId)
                } else {
                    state.dynamicProjects
                }
            state.copy(tasks = next, dynamicProjects = mergedProjects)
        }
        persistTasks(_uiState.value.tasks)
    }

    override fun onCleared() {
        unsubscribeTaskEvents()
        _pendingApproval.value = null
        super.onCleared()
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
