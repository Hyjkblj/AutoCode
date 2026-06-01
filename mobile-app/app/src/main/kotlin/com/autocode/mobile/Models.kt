package com.autocode.mobile

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Session(
    val accessToken: String,
    val displayName: String,
    val email: String? = null,
    val avatarUrl: String? = null,
    val provider: AuthProvider = AuthProvider.LOCAL,
)

@Serializable
enum class AuthProvider {
    @SerialName("local")
    LOCAL,
    @SerialName("github")
    GITHUB,
    @SerialName("google")
    GOOGLE,
    @SerialName("email")
    EMAIL,
}

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
        GenerationTarget.WEB -> "网页应用"
        GenerationTarget.WECHAT_MINI_PROGRAM -> "微信小程序"
    }

/** 创建任务时传入控制面的 agentProfile。 */
@Serializable
enum class AgentProfile {
    @SerialName("coder")
    CODER,

    @SerialName("ai-agent")
    AI_AGENT,
}

fun AgentProfile.apiValue(): String =
    when (this) {
        AgentProfile.CODER -> "coder"
        AgentProfile.AI_AGENT -> "ai-agent"
    }

fun AgentProfile.displayLabel(): String =
    when (this) {
        AgentProfile.CODER -> "代码助手"
        AgentProfile.AI_AGENT -> "智能代理"
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

/** 发布/版本历史（PR-3 占位：记录用户在 App 内触发的发布入口操作）。 */
@Serializable
data class PublishHistoryEntry(
    val id: String,
    val taskId: String,
    val artifactId: String? = null,
    val artifactName: String? = null,
    val sourceTaskId: String? = null,
    val versionLabel: String,
    val status: String,
    val environment: String? = null,
    val endpointUrl: String? = null,
    val deployRequestId: String? = null,
    val createdAt: Long,
)

/** PR-3：产物预览结构（仅用于界面展示，不持久化）。 */
data class ArtifactPreview(
    val title: String,
    val contentType: String?,
    val content: String,
    val truncated: Boolean,
    val byteSize: Int,
)

data class ArtifactAccessUrl(
    val url: String,
    val canonicalUrl: String? = null,
    val shareUrl: String? = null,
    val shortUrl: String? = null,
    val entryPath: String? = null,
    val tokenized: Boolean = false,
)

data class ApprovalRequest(
    val approvalId: String,
    val taskId: String,
    val action: String? = null,
    val tool: String? = null,
    val command: String? = null,
    val cwd: String? = null,
    val riskScore: Double? = null,
    val reason: String? = null,
    val timeoutSeconds: Int = 120,
    val createdAtMillis: Long = System.currentTimeMillis(),
)

// ── Super-Individual event payload models ──────────────────────────

data class ClarificationRequest(
    val question: String,
    val options: List<String>?,
    val context: String?,
    val stage: String?,
)

data class ClarificationAnswer(
    val answer: String,
    val originalQuestion: String?,
)

data class RepoBootstrapInfo(
    val repoUrl: String,
    val repoDir: String?,
    val fileCount: Int,
    val dependenciesInstalled: Boolean,
)

data class CodeIndexInfo(
    val fileCount: Int,
    val symbolCount: Int,
    val summary: String?,
)

data class PlanApprovalRequest(
    val planSummary: String,
    val steps: List<String>?,
    val estimatedImpact: String?,
)

data class TestGeneratedInfo(
    val testFile: String,
    val testCount: Int,
    val framework: String?,
)

data class KnowledgeWritebackInfo(
    val projectKey: String,
    val filesSummarized: Int,
    val errorPatternsStored: Int,
)
