package com.autocode.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.autocode.mobile.ApprovalRequest
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.TaskSource
import com.autocode.mobile.TaskStatus
import com.autocode.mobile.network.TaskEventDto
import com.autocode.mobile.ui.components.EventStatus
import com.autocode.mobile.ui.components.EventTimeline
import com.autocode.mobile.ui.components.LogColor
import com.autocode.mobile.ui.components.LogConsole
import com.autocode.mobile.ui.components.LogEntry
import com.autocode.mobile.ui.components.MobileUiTestTags
import com.autocode.mobile.ui.components.PipelineStage
import com.autocode.mobile.ui.components.PipelineStageInfo
import com autocode.mobile.ui.components.PipelineStepper
import com.autocode.mobile.ui.components.StageStatus
import com.autocode.mobile.ui.components.TimelineEventData
import com.autocode.mobile.ui.components.eventTypeLabel
import com.autocode.mobile.ui.components.payloadIntValue
import com.autocode.mobile.ui.components.payloadText
import com.autocode.mobile.ui.components.taskSourceLabel
import com.autocode.mobile.ui.components.taskStatusLabel
import kotlinx.coroutines.delay
import kotlinx.serialization.json.JsonObject
import java.time.Instant
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun TaskDetailTab(
    vm: AppViewModel,
    taskId: String,
    onBack: () -> Unit,
    innerNav: NavHostController,
) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val pendingApproval by vm.pendingApproval.collectAsStateWithLifecycle()
    val task = state.tasks.find { it.id == taskId }
    val events = state.taskEvents[taskId].orEmpty().sortedBy { it.seq }
    val fixTimeline = remember(events) { buildFixLoopTimeline(events) }
    val approvalForTask = pendingApproval?.takeIf { it.taskId == taskId }

    val pipelineStages = remember(events) { buildPipelineStages(events) }
    val timelineEvents = remember(events) { buildTimelineEvents(events) }
    val logEntries = remember(events) { buildLogEntries(events) }

    LaunchedEffect(taskId, state.baseUrl, state.session?.accessToken) {
        vm.subscribeTaskEvents(taskId)
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
        val scrollState = rememberScrollState()
        Column(
            Modifier
                .padding(pad)
                .padding(16.dp)
                .fillMaxSize()
                .verticalScroll(scrollState),
        ) {
            // Task prompt card
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                tonalElevation = 1.dp,
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text(task.prompt, style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Text("来源：${taskSourceLabel(task.source)}（本地模拟/控制面）")
                    Text("状态：${taskStatusLabel(task.status)}")
                    Text("进度：${task.progress}%")
                    Spacer(Modifier.height(8.dp))
                    LinearProgressIndicator(
                        progress = { task.progress / 100f },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            // PipelineStepper
            if (events.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                PipelineStepper(stages = pipelineStages)
            }

            // FixLoop timeline
            if (fixTimeline.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                FixLoopTimelineCard(points = fixTimeline)
            }

            // EventTimeline
            if (timelineEvents.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                EventTimeline(events = timelineEvents)
            }

            // LogConsole
            if (logEntries.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                LogConsole(entries = logEntries)
            }

            // View artifacts button
            if (task.status == TaskStatus.SUCCEEDED) {
                Spacer(Modifier.height(20.dp))
                TextButton(
                    onClick = { innerNav.navigate("artifacts/task/${task.id}") },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("查看产物")
                }
            }

            Spacer(Modifier.height(16.dp))
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ApprovalBottomSheet(
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
        modifier = Modifier.testTag(MobileUiTestTags.APPROVAL_SHEET),
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
            Text("审批编号：${approval.approvalId}", fontFamily = FontFamily.Monospace)
            approval.action?.let {
                Spacer(Modifier.height(6.dp))
                Text("动作：$it")
            }
            approval.tool?.let {
                Spacer(Modifier.height(6.dp))
                Text("工具：$it")
            }
            approval.command?.let {
                Spacer(Modifier.height(6.dp))
                Text("命令：$it", fontFamily = FontFamily.Monospace)
            }
            approval.cwd?.let {
                Spacer(Modifier.height(6.dp))
                Text("工作目录：$it", fontFamily = FontFamily.Monospace)
            }
            approval.riskScore?.let {
                Spacer(Modifier.height(6.dp))
                Text("风险分：${String.format(Locale.getDefault(), "%.2f", it)}")
            }
            approval.reason?.let {
                Spacer(Modifier.height(6.dp))
                Text("原因：$it")
            }

            Spacer(Modifier.height(14.dp))
            Text("剩余 ${secondsLeft} 秒", style = MaterialTheme.typography.labelLarge)
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
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .testTag(MobileUiTestTags.APPROVAL_COMMENT_INPUT),
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
                    modifier =
                        Modifier
                            .weight(1f)
                            .testTag(MobileUiTestTags.APPROVAL_APPROVE_BUTTON),
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
                    modifier =
                        Modifier
                            .weight(1f)
                            .testTag(MobileUiTestTags.APPROVAL_REJECT_BUTTON),
                ) {
                    Text("拒绝")
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

// ── Pipeline stage mapping ──────────────────────────────────────────

private data class StageDef(
    val stage: PipelineStage,
    val startTypes: Set<String>,
    val doneTypes: Set<String>,
)

private fun buildPipelineStages(events: List<TaskEventDto>): List<PipelineStageInfo> {
    val types = events.map { it.type?.uppercase().orEmpty() }.toSet()
    val hasFailed = "TASK_FAILED" in types
    val hasDone = "TASK_DONE" in types

    val stageOrder = listOf(
        StageDef(PipelineStage.BOOTSTRAP, setOf("REPO_BOOTSTRAP_STARTED"), setOf("REPO_BOOTSTRAP_DONE")),
        StageDef(PipelineStage.INDEX, setOf("CODE_INDEX_BUILT"), setOf("CODE_INDEX_BUILT")),
        StageDef(PipelineStage.CLARIFY, setOf("CLARIFICATION_REQUESTED"), setOf("CLARIFICATION_ANSWERED")),
        StageDef(PipelineStage.INTENT, setOf("TASK_STARTED"), setOf("TASK_STARTED")),
        StageDef(PipelineStage.PLAN, setOf("SPEC_PROPOSED", "PLAN_APPROVAL_REQUESTED"), setOf("SPEC_PROPOSED", "PLAN_APPROVAL_REQUESTED")),
        StageDef(PipelineStage.CODE, setOf("FILE_PATCH_PREVIEW"), setOf("FILE_PATCH_PREVIEW")),
        StageDef(PipelineStage.REVIEW, setOf("BUILD_STARTED"), setOf("BUILD_STARTED")),
        StageDef(PipelineStage.TEST, setOf("TEST_GENERATED"), setOf("TEST_GENERATED")),
        StageDef(PipelineStage.KNOWLEDGE, setOf("KNOWLEDGE_WRITEBACK"), setOf("KNOWLEDGE_WRITEBACK")),
    )

    // Find the last active stage index for FAILED tasks
    var lastActiveIdx = -1
    stageOrder.forEachIndexed { idx, def ->
        if (def.startTypes.intersect(types).isNotEmpty() || def.doneTypes.intersect(types).isNotEmpty()) {
            lastActiveIdx = idx
        }
    }

    return stageOrder.mapIndexed { idx, def ->
        val stageStatus = when {
            hasDone -> StageStatus.COMPLETED
            hasFailed -> when {
                idx < lastActiveIdx -> StageStatus.COMPLETED
                idx == lastActiveIdx -> StageStatus.FAILED
                else -> StageStatus.PENDING
            }
            def.doneTypes.intersect(types).isNotEmpty() -> StageStatus.COMPLETED
            def.startTypes.intersect(types).isNotEmpty() -> StageStatus.ACTIVE
            else -> StageStatus.PENDING
        }
        PipelineStageInfo(
            stage = def.stage,
            label = stageLabel(def.stage),
            status = stageStatus,
        )
    }
}

private fun stageLabel(stage: PipelineStage): String = when (stage) {
    PipelineStage.BOOTSTRAP -> "仓库初始化"
    PipelineStage.INDEX -> "代码索引"
    PipelineStage.CLARIFY -> "需求澄清"
    PipelineStage.INTENT -> "意图理解"
    PipelineStage.PLAN -> "方案规划"
    PipelineStage.CODE -> "代码生成"
    PipelineStage.REVIEW -> "代码审查"
    PipelineStage.TEST -> "测试生成"
    PipelineStage.KNOWLEDGE -> "知识回写"
}

// ── Timeline event mapping ──────────────────────────────────────────

private fun buildTimelineEvents(events: List<TaskEventDto>): List<TimelineEventData> {
    return events.mapNotNull { event ->
        val type = event.type?.uppercase().orEmpty()
        val status = when (type) {
            "TASK_DONE" -> EventStatus.SUCCESS
            "TASK_FAILED" -> EventStatus.FAILED
            "REPO_BOOTSTRAP_STARTED", "CLARIFICATION_REQUESTED", "BUILD_STARTED" -> EventStatus.ACTIVE
            else -> EventStatus.SUCCESS
        }
        val description = eventTypeLabel(event.type)
        val timestamp = event.timestamp?.let {
            runCatching { Instant.parse(it) }.getOrNull()
        } ?: Instant.now()

        TimelineEventData(
            timestamp = timestamp,
            type = event.type ?: "UNKNOWN",
            description = description,
            status = status,
        )
    }
}

// ── Log entry mapping ───────────────────────────────────────────────

private fun buildLogEntries(events: List<TaskEventDto>): List<LogEntry> {
    return events.map { event ->
        val type = event.type?.uppercase().orEmpty()
        val time = event.timestamp?.let {
            runCatching {
                val instant = Instant.parse(it)
                val cal = java.util.Calendar.getInstance()
                cal.timeInMillis = instant.toEpochMilli()
                String.format(
                    Locale.getDefault(),
                    "%02d:%02d:%02d",
                    cal.get(java.util.Calendar.HOUR_OF_DAY),
                    cal.get(java.util.Calendar.MINUTE),
                    cal.get(java.util.Calendar.SECOND),
                )
            }.getOrNull()
        } ?: "--:--:--"

        val (icon, color) = when (type) {
            "TASK_DONE" -> "✓" to LogColor.SUCCESS
            "TASK_FAILED" -> "⚡" to LogColor.WARNING
            "REPO_BOOTSTRAP_STARTED", "CLARIFICATION_REQUESTED", "BUILD_STARTED" -> "⏳" to LogColor.ACTIVE
            "REPO_BOOTSTRAP_DONE", "CODE_INDEX_BUILT", "CLARIFICATION_ANSWERED",
            "TEST_GENERATED", "KNOWLEDGE_WRITEBACK" -> "✓" to LogColor.SUCCESS
            else -> "→" to LogColor.INFO
        }

        LogEntry(
            timestamp = time,
            icon = icon,
            message = eventTypeLabel(event.type),
            color = color,
        )
    }
}

// ── FixLoop timeline ────────────────────────────────────────────────

private data class FixLoopPoint(
    val seq: Long,
    val title: String,
    val reason: String?,
    val riskLevel: String?,
    val errorCode: String?,
    val attempt: Int?,
    val maxAttempts: Int?,
)

private fun buildFixLoopTimeline(events: List<TaskEventDto>): List<FixLoopPoint> {
    val timeline = mutableListOf<FixLoopPoint>()
    events.forEach { event ->
        val type = event.type?.uppercase().orEmpty()
        val payload = event.payload
        val attempt = payloadIntValue(payload, "fixLoopAttempt", "attempt", "retryAttempt")
        val maxAttempts = payloadIntValue(payload, "maxAttempts", "retryMax", "maxRetry")
        val riskLevel = payloadText(payload, "riskLevel", "risk")
        val errorCode = payloadText(payload, "errorCode", "code")
        val reason = payloadText(payload, "reason", "message", "error")
        val hasStructuredData =
            attempt != null ||
                maxAttempts != null ||
                !riskLevel.isNullOrBlank() ||
                !errorCode.isNullOrBlank()
        if (!hasStructuredData && type !in setOf("TASK_FAILED", "TASK_DONE", "APPROVAL_REQUIRED")) return@forEach
        val title =
            when (type) {
                "TASK_FAILED" -> "执行失败"
                "TASK_DONE" -> "执行完成"
                "APPROVAL_REQUIRED" -> "等待审批"
                else -> event.type ?: "事件"
            }
        timeline +=
            FixLoopPoint(
                seq = event.seq,
                title = title,
                reason = reason,
                riskLevel = riskLevel,
                errorCode = errorCode,
                attempt = attempt,
                maxAttempts = maxAttempts,
            )
    }
    return timeline
        .sortedBy { it.seq }
        .takeLast(8)
}

@Composable
private fun FixLoopTimelineCard(points: List<FixLoopPoint>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            points.forEachIndexed { index, point ->
                if (index > 0) {
                    Spacer(Modifier.height(2.dp))
                }
                Text(
                    text = "Step ${index + 1} · ${point.title}",
                    style = MaterialTheme.typography.labelLarge,
                )
                point.reason?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall)
                }
                val meta = mutableListOf<String>()
                point.errorCode?.takeIf { it.isNotBlank() }?.let { meta += "errorCode=$it" }
                point.riskLevel?.takeIf { it.isNotBlank() }?.let { meta += "risk=$it" }
                if (point.attempt != null || point.maxAttempts != null) {
                    meta += "fixLoop=${point.attempt ?: "?"}/${point.maxAttempts ?: "?"}"
                }
                if (meta.isNotEmpty()) {
                    Text(
                        text = meta.joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = FontFamily.Monospace,
                    )
                }
            }
        }
    }
}
