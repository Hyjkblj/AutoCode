package com.autocode.mobile

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Session(
    val accessToken: String,
    val displayName: String,
)

/** 生成目标（PR-1）：写入创建任务时的 assistant 字段，供控制面区分 Web / 小程序等。 */
@Serializable
enum class GenerationTarget {
    @SerialName("web")
    WEB,

    @SerialName("wechat_mini")
    WECHAT_MINI_PROGRAM,
}

fun GenerationTarget.assistantForApi(): String =
    when (this) {
        GenerationTarget.WEB -> "web"
        GenerationTarget.WECHAT_MINI_PROGRAM -> "wechat_mini"
    }

fun GenerationTarget.displayLabel(): String =
    when (this) {
        GenerationTarget.WEB -> "Web 应用"
        GenerationTarget.WECHAT_MINI_PROGRAM -> "微信小程序"
    }

@Serializable
enum class TaskStatus {
    @SerialName("queued")
    QUEUED,

    @SerialName("running")
    RUNNING,

    @SerialName("succeeded")
    SUCCEEDED,

    @SerialName("failed")
    FAILED,
}

@Serializable
enum class TaskSource {
    @SerialName("local")
    LOCAL,

    @SerialName("remote")
    REMOTE,
}

@Serializable
data class TaskItem(
    val id: String,
    val projectId: String,
    val prompt: String,
    val status: TaskStatus,
    val progress: Int,
    val logs: List<String>,
    val createdAt: Long,
    val updatedAt: Long,
    val source: TaskSource = TaskSource.LOCAL,
)

data class Project(
    val id: String,
    val name: String,
)
