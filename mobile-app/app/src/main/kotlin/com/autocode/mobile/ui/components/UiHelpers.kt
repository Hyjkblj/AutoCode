package com.autocode.mobile.ui.components

import com.autocode.mobile.TaskSource
import com.autocode.mobile.TaskStatus
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

internal object MobileUiTestTags {
    const val VOICE_INPUT_BUTTON = "voice_input_button"
    const val EVENT_STREAM_LIST = "event_stream_list"
    const val APPROVAL_SHEET = "approval_sheet"
    const val APPROVAL_COMMENT_INPUT = "approval_comment_input"
    const val APPROVAL_APPROVE_BUTTON = "approval_approve_button"
    const val APPROVAL_REJECT_BUTTON = "approval_reject_button"
    const val NOTIFICATION_SWITCH = "notification_switch"
    const val ARTIFACT_PREVIEW_LOAD_BUTTON = "artifact_preview_load_button"
    const val ARTIFACT_PREVIEW_CARD = "artifact_preview_card"
}

internal fun taskSourceLabel(source: TaskSource): String =
    when (source) {
        TaskSource.LOCAL -> "本地"
        TaskSource.REMOTE -> "远程"
    }

internal fun taskStatusLabel(status: TaskStatus): String =
    when (status) {
        TaskStatus.QUEUED -> "排队中"
        TaskStatus.RUNNING -> "执行中"
        TaskStatus.SUCCEEDED -> "已完成"
        TaskStatus.FAILED -> "失败"
    }

internal fun publishStatusLabel(status: String): String {
    val normalized = status.trim().lowercase()
    return when (normalized) {
        "success", "succeeded", "done" -> "成功"
        "failed", "error" -> "失败"
        "queued" -> "排队中"
        "running" -> "执行中"
        "waiting_approval" -> "待审批"
        "deploy_planned" -> "已规划"
        "canceled", "cancelled" -> "已取消"
        "rejected" -> "已拒绝"
        else -> status
    }
}

internal fun genericStatusLabel(status: String): String {
    val normalized = status.trim().lowercase()
    return when (normalized) {
        "success", "succeeded", "done", "ok" -> "成功"
        "failed", "error" -> "失败"
        "queued" -> "排队中"
        "running" -> "执行中"
        "waiting_approval" -> "待审批"
        "deploy_planned" -> "已规划"
        "canceled", "cancelled" -> "已取消"
        "rejected" -> "已拒绝"
        "unknown" -> "未知"
        else -> status
    }
}

internal fun eventTypeLabel(type: String?): String {
    val normalized = type?.trim()?.uppercase().orEmpty()
    return when (normalized) {
        "ASSISTANT_OUTPUT" -> "助手输出"
        "TOOL_START" -> "工具调用开始"
        "TOOL_END" -> "工具调用结束"
        "FILE_PATCH_PREVIEW" -> "代码差异预览"
        "APPROVAL_REQUIRED" -> "等待审批"
        "DEPLOY_PLAN" -> "发布计划"
        "DEPLOY_RESULT" -> "发布结果"
        "TASK_RUNNING", "TASK_PROGRESS" -> "任务执行中"
        "TASK_DONE" -> "任务完成"
        "TASK_FAILED" -> "任务失败"
        "CLARIFICATION_REQUESTED" -> "需求澄清"
        "CLARIFICATION_ANSWERED" -> "澄清回复"
        "REPO_BOOTSTRAP_STARTED" -> "仓库初始化中"
        "REPO_BOOTSTRAP_DONE" -> "仓库初始化完成"
        "CODE_INDEX_BUILT" -> "代码索引构建完成"
        "PLAN_APPROVAL_REQUESTED" -> "计划审批"
        "TEST_GENERATED" -> "测试生成"
        "KNOWLEDGE_WRITEBACK" -> "知识回写"
        "" -> "事件"
        else -> type ?: "事件"
    }
}

internal fun environmentDisplayLabel(environment: String): String {
    val normalized = environment.trim().lowercase()
    return when (normalized) {
        "staging", "test", "testing" -> "测试环境"
        "prod", "production" -> "生产环境"
        "dev", "development" -> "开发环境"
        else -> environment
    }
}

internal fun normalizeEnvironmentForApi(environment: String): String {
    val trimmed = environment.trim()
    if (trimmed.isEmpty()) return "staging"
    return when (trimmed) {
        "测试环境" -> "staging"
        "生产环境" -> "production"
        "开发环境" -> "development"
        else -> trimmed
    }
}

internal fun defaultVersionLabel(): String =
    "v" + SimpleDateFormat("yyyyMMdd-HHmmss", Locale.getDefault()).format(Date())

internal fun formatTimestamp(millis: Long): String =
    runCatching {
        SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date(millis))
    }.getOrElse { millis.toString() }
