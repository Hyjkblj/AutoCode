package com.autocode.mobile.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.autocode.mobile.network.TaskEventDto
import com.mikepenz.markdown.coil3.Coil3ImageTransformerImpl
import com.mikepenz.markdown.compose.components.markdownComponents
import com.mikepenz.markdown.compose.elements.highlightedCodeBlock
import com.mikepenz.markdown.compose.elements.highlightedCodeFence
import com.mikepenz.markdown.m3.Markdown
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull

@Composable
internal fun AgentEventItem(event: TaskEventDto, fallbackLine: String) {
    val type = event.type?.uppercase().orEmpty()
    val payload = event.payload
    val header = "序号 ${event.seq} · ${eventTypeLabel(event.type)}"

    when (type) {
        "ASSISTANT_OUTPUT" -> {
            val agent = payloadText(payload, "agent", "assistant", "assistantName") ?: "助手"
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
            val tool = payloadText(payload, "tool", "toolName") ?: "未知工具"
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
                    Text("工具调用：$tool", style = MaterialTheme.typography.titleSmall)
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
                        Text("工作目录：$cwd", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
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
            val status = payloadText(payload, "status", "result")?.trim().orEmpty().ifBlank { "unknown" }
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
                    Text("状态：${genericStatusLabel(status)}")
                    execMs?.let {
                        Text("耗时：${it} 毫秒", fontFamily = FontFamily.Monospace)
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(header, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        "FILE_PATCH_PREVIEW" -> {
            val patch = payloadText(payload, "patch", "diff", "preview", "content")
            val patchLines = patch.orEmpty().lineSequence().toList()
            val previewLineLimit = 220
            val truncated = patchLines.size > previewLineLimit
            var expanded by rememberSaveable(eventStableKey(event)) { mutableStateOf(false) }
            val shownPatch =
                when {
                    patchLines.isEmpty() -> ""
                    expanded || !truncated -> patchLines.joinToString("\n")
                    else -> patchLines.take(previewLineLimit).joinToString("\n")
                }
            val markdownContent = remember(shownPatch) { asDiffMarkdown(shownPatch) }
            val mdComponents = remember {
                markdownComponents(
                    codeFence = highlightedCodeFence,
                    codeBlock = highlightedCodeBlock,
                )
            }
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
                    if (patchLines.isEmpty()) {
                        Text("暂无差异内容", fontFamily = FontFamily.Monospace)
                    } else {
                        Markdown(
                            content = markdownContent,
                            modifier = Modifier.fillMaxWidth(),
                            imageTransformer = Coil3ImageTransformerImpl,
                            components = mdComponents,
                        )
                        if (truncated) {
                            Spacer(Modifier.height(6.dp))
                            TextButton(onClick = { expanded = !expanded }) {
                                Text(if (expanded) "收起完整差异" else "展开完整差异")
                            }
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
                        Text("动作：$it")
                    }
                    command?.let {
                        Spacer(Modifier.height(6.dp))
                        Text("命令：$it", fontFamily = FontFamily.Monospace)
                    }
                    reason?.let {
                        Spacer(Modifier.height(6.dp))
                        Text("原因：$it")
                    }
                }
            }
        }
        "DEPLOY_PLAN" -> {
            val environment = payloadText(payload, "environment", "env") ?: "测试环境"
            val artifactId = payloadText(payload, "artifactId")
            val version = payloadText(payload, "version", "versionLabel")
            val requestId = payloadText(payload, "requestId", "deployRequestId", "request_id")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("发布计划", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("环境：${environmentDisplayLabel(environment)}")
                    artifactId?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("产物：$it", fontFamily = FontFamily.Monospace)
                    }
                    version?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("版本：$it")
                    }
                    requestId?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("请求编号：$it", fontFamily = FontFamily.Monospace)
                    }
                }
            }
        }
        "DEPLOY_RESULT" -> {
            val rawStatus = payloadText(payload, "status", "result") ?: "unknown"
            val status = rawStatus.trim().ifEmpty { "unknown" }
            val normalized = status.lowercase()
            val endpoint = payloadText(payload, "endpointUrl", "endpoint", "url")
            val requestId = payloadText(payload, "requestId", "deployRequestId", "request_id")
            val reason = payloadText(payload, "reason", "message", "error")
            val cardColor =
                when (normalized) {
                    "success", "succeeded", "done", "ok" -> MaterialTheme.colorScheme.tertiaryContainer
                    "failed", "error", "rejected", "canceled", "cancelled" -> MaterialTheme.colorScheme.errorContainer
                    else -> MaterialTheme.colorScheme.secondaryContainer
                }
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = cardColor,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("发布结果", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("状态：${genericStatusLabel(status)}")
                    endpoint?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("访问地址：$it", fontFamily = FontFamily.Monospace)
                    }
                    requestId?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("请求编号：$it", fontFamily = FontFamily.Monospace)
                    }
                    reason?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("原因：$it")
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
                    if (!done) {
                        val errorCode = payloadText(payload, "errorCode", "code")
                        val riskLevel = payloadText(payload, "riskLevel", "risk")
                        val attempt = payloadIntValue(payload, "fixLoopAttempt", "attempt", "retryAttempt")
                        val maxAttempts = payloadIntValue(payload, "maxAttempts", "retryMax", "maxRetry")
                        val issues = payloadTextList(payload, "issues")
                        errorCode?.let {
                            Spacer(Modifier.height(6.dp))
                            Text("错误码：$it", fontFamily = FontFamily.Monospace)
                        }
                        riskLevel?.let {
                            Spacer(Modifier.height(4.dp))
                            Text("风险等级：$it")
                        }
                        if (attempt != null || maxAttempts != null) {
                            Spacer(Modifier.height(4.dp))
                            val progressLabel =
                                if (attempt != null && maxAttempts != null) "$attempt/$maxAttempts"
                                else "${attempt ?: "?"}/${maxAttempts ?: "?"}"
                            Text("修复轮次：$progressLabel", fontFamily = FontFamily.Monospace)
                        }
                        if (issues.isNotEmpty()) {
                            Spacer(Modifier.height(4.dp))
                            Text("问题列表：")
                            issues.take(5).forEach { issue ->
                                Text("- $issue", style = MaterialTheme.typography.bodySmall)
                            }
                            if (issues.size > 5) {
                                Text("- ...（还有 ${issues.size - 5} 条）", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(header, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        "CLARIFICATION_REQUESTED" -> {
            val question = payloadText(payload, "question") ?: "需要澄清"
            val options = payloadTextList(payload, "options")
            val context = payloadText(payload, "context")
            val stage = payloadText(payload, "stage")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("需求澄清", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text(question)
                    if (options.isNotEmpty()) {
                        Spacer(Modifier.height(6.dp))
                        Text("可选回答：", style = MaterialTheme.typography.labelMedium)
                        options.forEach { opt ->
                            Text("- $opt", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    context?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("背景：$it", style = MaterialTheme.typography.bodySmall)
                    }
                    stage?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("阶段：$it", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        "CLARIFICATION_ANSWERED" -> {
            val answer = payloadText(payload, "answer") ?: "已回答"
            val originalQuestion = payloadText(payload, "originalQuestion")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("澄清回复", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text(answer)
                    originalQuestion?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("原问题：$it", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        "REPO_BOOTSTRAP_STARTED" -> {
            val repoUrl = payloadText(payload, "repoUrl") ?: ""
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("仓库初始化中", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    if (repoUrl.isNotBlank()) {
                        Spacer(Modifier.height(6.dp))
                        Text("仓库地址：$repoUrl", fontFamily = FontFamily.Monospace)
                    }
                    Spacer(Modifier.height(6.dp))
                    CircularProgressIndicator(modifier = Modifier.height(16.dp))
                }
            }
        }
        "REPO_BOOTSTRAP_DONE" -> {
            val repoUrl = payloadText(payload, "repoUrl") ?: ""
            val fileCount = payloadLongValue(payload, "fileCount") ?: 0L
            val depsInstalled = payloadText(payload, "dependenciesInstalled")?.toBooleanStrictOrNull() ?: false
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("仓库初始化完成", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("文件数量：$fileCount")
                    Text("依赖安装：${if (depsInstalled) "已完成" else "未完成"}")
                    repoUrl.takeIf { it.isNotBlank() }?.let {
                        Text("仓库：$it", fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        "CODE_INDEX_BUILT" -> {
            val fileCount = payloadLongValue(payload, "fileCount") ?: 0L
            val symbolCount = payloadLongValue(payload, "symbolCount") ?: 0L
            val summary = payloadText(payload, "summary")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("代码索引构建完成", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("文件：$fileCount  符号：$symbolCount")
                    summary?.let {
                        Spacer(Modifier.height(4.dp))
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        "PLAN_APPROVAL_REQUESTED" -> {
            val planSummary = payloadText(payload, "planSummary") ?: "执行计划待审批"
            val steps = payloadTextList(payload, "steps")
            val estimatedImpact = payloadText(payload, "estimatedImpact")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("计划审批", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text(planSummary)
                    if (steps.isNotEmpty()) {
                        Spacer(Modifier.height(6.dp))
                        Text("执行步骤：", style = MaterialTheme.typography.labelMedium)
                        steps.forEachIndexed { idx, step ->
                            Text("${idx + 1}. $step", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    estimatedImpact?.let {
                        Spacer(Modifier.height(4.dp))
                        Text("预计影响：$it", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        "TEST_GENERATED" -> {
            val testFile = payloadText(payload, "testFile") ?: "测试文件"
            val testCount = payloadLongValue(payload, "testCount") ?: 0L
            val framework = payloadText(payload, "framework")
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("测试生成", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("测试文件：$testFile", fontFamily = FontFamily.Monospace)
                    Text("用例数量：$testCount")
                    framework?.let {
                        Text("框架：$it")
                    }
                }
            }
        }
        "KNOWLEDGE_WRITEBACK" -> {
            val projectKey = payloadText(payload, "projectKey") ?: ""
            val filesSummarized = payloadLongValue(payload, "filesSummarized") ?: 0L
            val errorPatternsStored = payloadLongValue(payload, "errorPatternsStored") ?: 0L
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                    ),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text("知识回写完成", style = MaterialTheme.typography.titleSmall)
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("文件摘要：$filesSummarized  错误模式：$errorPatternsStored")
                    projectKey.takeIf { it.isNotBlank() }?.let {
                        Text("项目：$it", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        else -> {
            Card {
                Column(Modifier.padding(12.dp)) {
                    Text(header, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(6.dp))
                    Text("暂无差异内容", fontFamily = FontFamily.Monospace)
                }
            }
        }
    }
}

internal fun eventStableKey(event: TaskEventDto): String =
    when {
        !event.eventId.isNullOrBlank() -> "id:${event.eventId}"
        event.seq > 0L -> "seq:${event.seq}"
        else -> "raw:${event.type}:${event.timestamp}:${event.payload}"
    }

internal fun payloadText(payload: JsonObject, vararg keys: String): String? {
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

internal fun payloadLongValue(payload: JsonObject, vararg keys: String): Long? {
    keys.forEach { key ->
        val value = payload[key]?.jsonPrimitive?.longOrNull
        if (value != null) return value
    }
    return null
}

internal fun payloadIntValue(payload: JsonObject, vararg keys: String): Int? {
    keys.forEach { key ->
        val primitive = payload[key]?.jsonPrimitive ?: return@forEach
        primitive.longOrNull?.toInt()?.let { return it }
        primitive.doubleOrNull?.toInt()?.let { return it }
        primitive.contentOrNull?.trim()?.toIntOrNull()?.let { return it }
    }
    return null
}

internal fun payloadTextList(payload: JsonObject, vararg keys: String): List<String> {
    keys.forEach { key ->
        val element = payload[key] ?: return@forEach
        val fromArray =
            (element as? JsonArray)
                ?.mapNotNull { it.jsonPrimitive.contentOrNull?.trim() }
                ?.filter { it.isNotEmpty() }
                .orEmpty()
        if (fromArray.isNotEmpty()) return fromArray
        val single = element.jsonPrimitive.contentOrNull?.trim().orEmpty()
        if (single.isNotEmpty()) {
            return single
                .split('\n', ';')
                .map { it.trim() }
                .filter { it.isNotEmpty() }
        }
    }
    return emptyList()
}
