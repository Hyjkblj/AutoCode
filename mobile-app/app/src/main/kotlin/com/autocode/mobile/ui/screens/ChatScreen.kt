package com.autocode.mobile.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.*
import com.autocode.mobile.network.CODE_INDEX_BUILT
import com.autocode.mobile.network.CLARIFICATION_REQUESTED
import com.autocode.mobile.network.PLAN_APPROVAL_REQUESTED
import com.autocode.mobile.network.TaskEventDto
import com.autocode.mobile.network.TEST_GENERATED
import com.autocode.mobile.ui.components.*
import kotlinx.coroutines.launch
import java.time.Instant
import java.util.UUID

@Composable
fun ChatScreen(vm: AppViewModel) {
    val uiState by vm.uiState.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    val coroutineScope = rememberCoroutineScope()
    var inputText by remember { mutableStateOf("") }

    // Build chat messages from tasks and events
    val chatMessages = remember(uiState.tasks, uiState.taskEvents) {
        buildChatMessages(uiState.tasks, uiState.taskEvents)
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Header
        ChatHeader()

        // Message list
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            state = listState,
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 12.dp)
        ) {
            items(chatMessages, key = { it.id }) { message ->
                AnimatedVisibility(
                    visible = true,
                    enter = fadeIn() + slideInVertically { it / 2 }
                ) {
                    ChatMessageItem(message = message, vm = vm)
                }
            }
        }

        // Input bar
        ChatInputBar(
            value = inputText,
            onValueChange = { inputText = it },
            onSend = {
                if (inputText.isNotBlank()) {
                    val prompt = inputText
                    inputText = ""
                    coroutineScope.launch {
                        vm.createTaskAsync(prompt)
                        listState.animateScrollToItem(chatMessages.lastIndex + 1)
                    }
                }
            }
        )
    }
}

@Composable
private fun ChatHeader() {
    Surface(
        tonalElevation = 2.dp,
        shadowElevation = 4.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.SmartToy,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.onPrimaryContainer
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    text = "AI Agent",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.tertiary)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "在线",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun ChatMessageItem(
    message: ChatScreenMessage,
    vm: AppViewModel
) {
    when {
        message.role == MessageRole.SYSTEM -> {
            SystemMessage(text = message.content)
        }
        message.role == MessageRole.USER -> {
            ChatBubble(message = message.toChatMessageData())
        }
        else -> {
            // Assistant message -- could be text, task card, clarification, etc.
            AssistantMessageContent(message = message, vm = vm)
        }
    }
}

@Composable
private fun AssistantMessageContent(
    message: ChatScreenMessage,
    vm: AppViewModel
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Start
    ) {
        // Avatar
        Box(
            modifier = Modifier
                .size(32.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primaryContainer),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Filled.SmartToy,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
                tint = MaterialTheme.colorScheme.onPrimaryContainer
            )
        }

        Spacer(modifier = Modifier.width(8.dp))

        // Content
        Column(modifier = Modifier.widthIn(max = 300.dp)) {
            Surface(
                shape = RoundedCornerShape(16.dp, 16.dp, 16.dp, 4.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                tonalElevation = 1.dp
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(
                        text = message.content,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // Embedded components
            message.task?.let { task ->
                Spacer(modifier = Modifier.height(8.dp))
                EmbeddedTaskCard(task = task)
            }

            message.clarification?.let { clarification ->
                Spacer(modifier = Modifier.height(8.dp))
                ClarificationCard(
                    data = ClarificationData(
                        question = clarification.question,
                        options = clarification.options,
                        context = clarification.context,
                        stage = clarification.stage
                    ),
                    onAnswer = { answer ->
                        // TODO: wire to ViewModel when submitClarificationAnswer is available
                    }
                )
            }

            message.planApproval?.let { plan ->
                Spacer(modifier = Modifier.height(8.dp))
                PlanApprovalCard(
                    plan = plan,
                    onApprove = {
                        // Use task context if available; approvalId left empty as placeholder
                        val taskId = message.task?.id ?: ""
                        vm.submitApproval(taskId, "", "approve")
                    },
                    onReject = {
                        val taskId = message.task?.id ?: ""
                        vm.submitApproval(taskId, "", "reject")
                    }
                )
            }

            message.testResult?.let { test ->
                Spacer(modifier = Modifier.height(8.dp))
                TestResultCard(test = test)
            }

            message.codeIndex?.let { index ->
                Spacer(modifier = Modifier.height(8.dp))
                CodeIndexCard(
                    data = CodeIndexData(
                        fileCount = index.fileCount,
                        symbolCount = index.symbolCount,
                        summary = index.summary
                    )
                )
            }
        }
    }
}

@Composable
private fun EmbeddedTaskCard(task: TaskItem) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 2.dp
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = task.prompt.take(30) + if (task.prompt.length > 30) "..." else "",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium
                )
                TaskStatusChip(status = task.status)
            }
            if (task.status == TaskStatus.RUNNING) {
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = { (task.progress.coerceIn(0, 100)) / 100f },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp)),
                    color = MaterialTheme.colorScheme.primaryContainer,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun TaskStatusChip(status: TaskStatus) {
    val (text, color) = when (status) {
        TaskStatus.QUEUED -> "队列中" to MaterialTheme.colorScheme.outline
        TaskStatus.RUNNING -> "运行中" to MaterialTheme.colorScheme.primary
        TaskStatus.SUCCEEDED -> "已完成" to MaterialTheme.colorScheme.tertiary
        TaskStatus.FAILED -> "失败" to MaterialTheme.colorScheme.error
    }
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = color.copy(alpha = 0.1f)
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
            style = MaterialTheme.typography.labelSmall,
            color = color
        )
    }
}

@Composable
private fun PlanApprovalCard(
    plan: PlanApprovalRequest,
    onApprove: () -> Unit,
    onReject: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f),
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.Gavel,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = MaterialTheme.colorScheme.error
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "方案待审批",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.error
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = plan.planSummary,
                style = MaterialTheme.typography.bodySmall
            )
            if (!plan.steps.isNullOrEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                plan.steps.forEachIndexed { index, step ->
                    Row(modifier = Modifier.padding(vertical = 2.dp)) {
                        Text(
                            text = "${index + 1}.",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.width(20.dp)
                        )
                        Text(
                            text = step,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onApprove,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("批准")
                }
                OutlinedButton(
                    onClick = onReject,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("拒绝")
                }
            }
        }
    }
}

@Composable
private fun TestResultCard(test: TestGeneratedInfo) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.CheckCircle,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = MaterialTheme.colorScheme.tertiary
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "测试通过",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.surface,
                    modifier = Modifier.weight(1f)
                ) {
                    Column(
                        modifier = Modifier.padding(8.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = test.testCount.toString(),
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.tertiary
                        )
                        Text(
                            text = "测试",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.surface,
                    modifier = Modifier.weight(1f)
                ) {
                    Column(
                        modifier = Modifier.padding(8.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = test.framework ?: "jest",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Medium
                        )
                        Text(
                            text = "框架",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatInputBar(
    value: String,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit
) {
    Surface(
        tonalElevation = 3.dp,
        shadowElevation = 8.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp)
                .imePadding(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = {
                    Text(
                        "输入任务描述...",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
                    )
                },
                shape = RoundedCornerShape(24.dp),
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyMedium,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primaryContainer,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant
                )
            )
            Spacer(modifier = Modifier.width(8.dp))
            FilledIconButton(
                onClick = onSend,
                enabled = value.isNotBlank(),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Send,
                    contentDescription = "发送"
                )
            }
        }
    }
}

// ── Chat message data ──

data class ChatScreenMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: MessageRole,
    val content: String,
    val timestamp: Instant = Instant.now(),
    val task: TaskItem? = null,
    val clarification: ClarificationRequest? = null,
    val planApproval: PlanApprovalRequest? = null,
    val testResult: TestGeneratedInfo? = null,
    val codeIndex: CodeIndexInfo? = null,
) {
    fun toChatMessageData(): ChatMessageData = ChatMessageData(
        id = id,
        role = role,
        content = content,
        timestamp = timestamp
    )
}

// ── Message builder ──

private fun buildChatMessages(
    tasks: List<TaskItem>,
    taskEvents: Map<String, List<TaskEventDto>>
): List<ChatScreenMessage> {
    val messages = mutableListOf<ChatScreenMessage>()

    // Welcome message
    messages.add(
        ChatScreenMessage(
            role = MessageRole.ASSISTANT,
            content = "你好！我是 AutoCode AI Agent。我可以帮你生成代码、自动测试、一键部署。请描述你的需求。"
        )
    )

    // Convert tasks to chat messages
    tasks.forEach { task ->
        // User message
        messages.add(
            ChatScreenMessage(
                role = MessageRole.USER,
                content = task.prompt,
                task = task
            )
        )

        // Assistant acknowledgment for running/queued tasks
        if (task.status == TaskStatus.RUNNING || task.status == TaskStatus.QUEUED) {
            messages.add(
                ChatScreenMessage(
                    role = MessageRole.ASSISTANT,
                    content = "收到，正在处理你的任务…",
                    task = task
                )
            )
        }

        // Events for this task
        val events = taskEvents[task.id] ?: emptyList()
        events.forEach { event ->
            val type = event.type?.uppercase().orEmpty()
            when (type) {
                CLARIFICATION_REQUESTED -> {
                    val question = stringValue(event.payload, "question") ?: "需要澄清"
                    val options = stringListValue(event.payload, "options")
                    val context = stringValue(event.payload, "context")
                    val stage = stringValue(event.payload, "stage")
                    messages.add(
                        ChatScreenMessage(
                            role = MessageRole.ASSISTANT,
                            content = "需要澄清",
                            clarification = ClarificationRequest(
                                question = question,
                                options = options,
                                context = context,
                                stage = stage
                            )
                        )
                    )
                }
                PLAN_APPROVAL_REQUESTED -> {
                    val summary = stringValue(event.payload, "planSummary")
                        ?: stringValue(event.payload, "summary")
                        ?: "执行计划待审批"
                    val steps = stringListValue(event.payload, "steps")
                    val impact = stringValue(event.payload, "estimatedImpact")
                    messages.add(
                        ChatScreenMessage(
                            role = MessageRole.ASSISTANT,
                            content = "方案待审批",
                            task = task,
                            planApproval = PlanApprovalRequest(
                                planSummary = summary,
                                steps = steps,
                                estimatedImpact = impact
                            )
                        )
                    )
                }
                TEST_GENERATED -> {
                    val testFile = stringValue(event.payload, "testFile") ?: ""
                    val testCount = longValue(event.payload, "testCount")?.toInt() ?: 0
                    val framework = stringValue(event.payload, "framework")
                    messages.add(
                        ChatScreenMessage(
                            role = MessageRole.ASSISTANT,
                            content = "测试生成完成",
                            testResult = TestGeneratedInfo(
                                testFile = testFile,
                                testCount = testCount,
                                framework = framework
                            )
                        )
                    )
                }
                CODE_INDEX_BUILT -> {
                    val fileCount = longValue(event.payload, "fileCount")?.toInt() ?: 0
                    val symbolCount = longValue(event.payload, "symbolCount")?.toInt() ?: 0
                    val summary = stringValue(event.payload, "summary")
                    messages.add(
                        ChatScreenMessage(
                            role = MessageRole.ASSISTANT,
                            content = "代码索引完成",
                            codeIndex = CodeIndexInfo(
                                fileCount = fileCount,
                                symbolCount = symbolCount,
                                summary = summary
                            )
                        )
                    )
                }
                "TASK_DONE" -> {
                    messages.add(
                        ChatScreenMessage(
                            role = MessageRole.SYSTEM,
                            content = "✅ 任务完成"
                        )
                    )
                }
                "TASK_FAILED" -> {
                    val reason = stringValue(event.payload, "reason", "message", "error")
                    val suffix = if (!reason.isNullOrBlank()) "：$reason" else ""
                    messages.add(
                        ChatScreenMessage(
                            role = MessageRole.SYSTEM,
                            content = "❌ 任务失败$suffix"
                        )
                    )
                }
            }
        }
    }

    return messages
}

// ── Payload extraction helpers ──

private fun stringValue(payload: kotlinx.serialization.json.JsonObject, vararg keys: String): String? {
    for (key in keys) {
        val primitive = payload[key] as? kotlinx.serialization.json.JsonPrimitive ?: continue
        val raw = primitive.contentOrNull?.trim().orEmpty()
        if (raw.isNotEmpty()) return raw
    }
    return null
}

private fun longValue(payload: kotlinx.serialization.json.JsonObject, vararg keys: String): Long? {
    for (key in keys) {
        val primitive = payload[key] as? kotlinx.serialization.json.JsonPrimitive ?: continue
        primitive.longOrNull?.let { return it }
        primitive.doubleOrNull?.toLong()?.let { return it }
        primitive.contentOrNull?.trim()?.toLongOrNull()?.let { return it }
    }
    return null
}

private fun stringListValue(payload: kotlinx.serialization.json.JsonObject, key: String): List<String>? {
    val array = payload[key] as? kotlinx.serialization.json.JsonArray ?: return null
    return array.mapNotNull { element ->
        (element as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull?.trim()?.takeIf { it.isNotEmpty() }
    }.takeIf { it.isNotEmpty() }
}
