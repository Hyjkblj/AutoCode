package com.autocode.mobile.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * 最小控制面 HTTP 客户端（PR-2：任务；PR-3：产物列表）。
 * 需控制面开启 `mvp.auth.mode=jwt` 且提供 `/api/v1/auth/login`。
 */
object ControlPlaneClient {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    private val client: OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

    private val mediaJson = "application/json; charset=utf-8".toMediaType()

    fun normalizeBaseUrl(url: String): String = url.trim().trimEnd('/')

    suspend fun login(baseUrl: String, username: String, password: String): Result<String> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val body =
                    buildJsonObject {
                        put("username", username.trim())
                        put("password", password)
                    }.toString()
                val req =
                    Request.Builder()
                        .url("$root/api/v1/auth/login")
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(200)}")
                    }
                    parseAccessToken(text)
                }
            }
        }

    suspend fun createTask(
        baseUrl: String,
        bearerToken: String,
        projectId: String,
        prompt: String,
        assistant: String,
    ): Result<TaskSummaryDto> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val body =
                    buildJsonObject {
                        put("projectId", projectId.trim())
                        put("prompt", prompt.trim())
                        put("assistant", assistant.trim())
                        put("inputMode", "voice_text")
                        put("riskPolicy", "strict_approval")
                    }.toString()
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseTaskSummaryEnvelope(text)
                }
            }
        }

    suspend fun createDeployTask(
        baseUrl: String,
        bearerToken: String,
        projectId: String,
        artifactId: String?,
        environment: String,
        versionLabel: String,
        sourceTaskId: String?,
    ): Result<TaskSummaryDto> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val normalizedProjectId = projectId.trim()
                val normalizedArtifactId = artifactId?.trim().orEmpty().ifBlank { "unknown-artifact" }
                val normalizedEnvironment = environment.trim().ifBlank { "staging" }
                val normalizedVersion = versionLabel.trim().ifBlank { "v-${System.currentTimeMillis()}" }
                val prompt =
                    buildString {
                        append("Deploy artifact ")
                        append(normalizedArtifactId)
                        append(" to ")
                        append(normalizedEnvironment)
                        append(" with version ")
                        append(normalizedVersion)
                        sourceTaskId?.trim()?.takeIf { it.isNotEmpty() }?.let {
                            append(" (sourceTaskId=")
                            append(it)
                            append(')')
                        }
                    }
                val body =
                    buildJsonObject {
                        put("projectId", normalizedProjectId)
                        put("prompt", prompt)
                        put("assistant", "deployer")
                        put("agentProfile", "deployer")
                        put("inputMode", "publish")
                        put("riskPolicy", "strict_approval")
                        put("sessionKey", "deploy:$normalizedProjectId")
                    }.toString()
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseTaskSummaryEnvelope(text)
                }
            }
        }

    suspend fun listProjects(
        baseUrl: String,
        bearerToken: String,
    ): Result<List<ProjectSummaryDto>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val req =
                    Request.Builder()
                        .url("$root/api/v1/projects")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseProjectListEnvelope(text)
                }
            }
        }

    suspend fun listAgentNodes(
        baseUrl: String,
        bearerToken: String,
    ): Result<List<AgentNodeDto>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val req =
                    Request.Builder()
                        .url("$root/api/v1/agent/nodes")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseAgentNodeListEnvelope(text)
                }
            }
        }

    suspend fun listArtifacts(
        baseUrl: String,
        bearerToken: String,
        taskId: String,
    ): Result<List<ArtifactListItem>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks/${taskId.trim()}/artifacts")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseGatewayArtifactList(text, taskId.trim())
                }
            }
        }

    suspend fun downloadArtifact(
        baseUrl: String,
        bearerToken: String,
        taskId: String,
        artifactId: String,
    ): Result<ArtifactDownloadData> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks/${taskId.trim()}/artifacts/${artifactId.trim()}/download")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val bytes = resp.body?.bytes() ?: ByteArray(0)
                    if (resp.code == 404) {
                        error("产物不存在或无权访问 (404)")
                    }
                    if (!resp.isSuccessful) {
                        val txt = bytes.toString(Charsets.UTF_8).take(300)
                        error("HTTP ${resp.code}: $txt")
                    }
                    ArtifactDownloadData(
                        bytes = bytes,
                        contentType = resp.header("Content-Type"),
                        fileName = parseDownloadFilename(resp.header("Content-Disposition")),
                    )
                }
            }
        }

    suspend fun getTask(
        baseUrl: String,
        bearerToken: String,
        taskId: String,
    ): Result<TaskSummaryDto> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks/${taskId.trim()}")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) {
                        error("任务不存在或无权访问 (404)")
                    }
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseTaskSummaryEnvelope(text)
                }
            }
        }

    suspend fun listTaskEvents(
        baseUrl: String,
        bearerToken: String,
        taskId: String,
        lastSeq: Long,
    ): Result<List<TaskEventDto>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val seq = maxOf(0L, lastSeq)
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks/${taskId.trim()}/events?lastSeq=$seq")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) {
                        error("任务不存在或无权访问 (404)")
                    }
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseTaskEventsEnvelope(text)
                }
            }
        }

    suspend fun submitApproval(
        baseUrl: String,
        bearerToken: String,
        taskId: String,
        approvalId: String,
        decision: String,
        comment: String?,
    ): Result<TaskSummaryDto> =
        withContext(Dispatchers.IO) {
            runCatching {
                val root = normalizeBaseUrl(baseUrl)
                val body =
                    buildJsonObject {
                        put("approvalId", approvalId.trim())
                        put("decision", decision.trim())
                        comment?.trim()?.takeIf { it.isNotEmpty() }?.let { put("comment", it) }
                    }.toString()
                val req =
                    Request.Builder()
                        .url("$root/api/v1/tasks/${taskId.trim()}/approval")
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) {
                        error("任务不存在、审批单不存在或无权访问 (404)")
                    }
                    if (!resp.isSuccessful) {
                        error("HTTP ${resp.code}: ${text.take(300)}")
                    }
                    parseTaskSummaryEnvelope(text)
                }
            }
        }

    private fun parseAccessToken(responseBody: String): String {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            val err = obj["error"]?.jsonPrimitive?.contentOrNull ?: "登录失败"
            error(err)
        }
        val payload = obj["payload"]?.jsonObject ?: error("登录响应缺少 payload")
        val token = payload["accessToken"]?.jsonPrimitive?.contentOrNull
        if (token.isNullOrBlank()) {
            error("登录响应缺少 accessToken（需 mvp.auth.mode=jwt）")
        }
        return token
    }

    private fun parseTaskSummaryEnvelope(responseBody: String): TaskSummaryDto {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            val err = obj["error"]?.jsonPrimitive?.contentOrNull ?: "请求失败"
            error(err)
        }
        val payload = obj["payload"]?.jsonObject ?: error("响应缺少 payload")
        return parseTaskSummary(payload)
    }

    private fun parseTaskSummary(o: JsonObject): TaskSummaryDto {
        val taskId = o["taskId"]?.jsonPrimitive?.contentOrNull ?: error("缺少 taskId")
        val status = o["status"]?.jsonPrimitive?.contentOrNull ?: "UNKNOWN"
        return TaskSummaryDto(
            taskId = taskId,
            projectId = o["projectId"]?.jsonPrimitive?.contentOrNull,
            prompt = o["prompt"]?.jsonPrimitive?.contentOrNull,
            status = status,
            assistant = o["assistant"]?.jsonPrimitive?.contentOrNull,
            agentProfile = o["agentProfile"]?.jsonPrimitive?.contentOrNull,
        )
    }

    private fun parseProjectListEnvelope(responseBody: String): List<ProjectSummaryDto> {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            val err = obj["error"]?.jsonPrimitive?.contentOrNull ?: "request failed"
            error(err)
        }
        val payload = obj["payload"]?.jsonArray ?: return emptyList()
        return payload.mapNotNull { el ->
            val o = el.jsonObject
            val projectId = o["projectId"]?.jsonPrimitive?.contentOrNull?.trim().orEmpty()
            if (projectId.isEmpty()) return@mapNotNull null
            ProjectSummaryDto(
                projectId = projectId,
                name = o["name"]?.jsonPrimitive?.contentOrNull,
                roleName = o["roleName"]?.jsonPrimitive?.contentOrNull,
            )
        }
    }

    private fun parseAgentNodeListEnvelope(responseBody: String): List<AgentNodeDto> {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            val err = obj["error"]?.jsonPrimitive?.contentOrNull ?: "request failed"
            error(err)
        }
        val payload = obj["payload"]?.jsonArray ?: return emptyList()
        return payload.mapNotNull { el ->
            val o = el.jsonObject
            val nodeId = o["nodeId"]?.jsonPrimitive?.contentOrNull?.trim().orEmpty()
            if (nodeId.isEmpty()) return@mapNotNull null
            AgentNodeDto(
                nodeId = nodeId,
                version = o["version"]?.jsonPrimitive?.contentOrNull,
                capabilities = o["capabilities"]?.jsonPrimitive?.contentOrNull,
                lastHeartbeatAt = o["lastHeartbeatAt"]?.jsonPrimitive?.contentOrNull,
                online = o["online"]?.jsonPrimitive?.booleanOrNull == true,
            )
        }
    }

    private fun parseGatewayArtifactList(body: String, fallbackTaskId: String): List<ArtifactListItem> {
        val obj = json.parseToJsonElement(body).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            error(obj["error"]?.jsonPrimitive?.contentOrNull ?: "产物列表失败")
        }
        val payload = obj["payload"]?.jsonObject ?: error("响应缺少 payload")
        val tid = payload["taskId"]?.jsonPrimitive?.contentOrNull ?: fallbackTaskId
        val items = payload["items"]?.jsonArray ?: return emptyList()
        return items.map { el ->
            val o = el.jsonObject
            ArtifactListItem(
                artifactId = o["artifactId"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                taskId = o["taskId"]?.jsonPrimitive?.contentOrNull ?: tid,
                name = o["name"]?.jsonPrimitive?.contentOrNull,
                contentType = o["contentType"]?.jsonPrimitive?.contentOrNull,
                sizeBytes = o["sizeBytes"]?.jsonPrimitive?.longOrNull,
                sha256 = o["sha256"]?.jsonPrimitive?.contentOrNull,
            )
        }
    }

    private fun parseTaskEventsEnvelope(responseBody: String): List<TaskEventDto> {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            val err = obj["error"]?.jsonPrimitive?.contentOrNull ?: "请求失败"
            error(err)
        }
        val payload = obj["payload"]?.jsonArray ?: return emptyList()
        return payload.mapNotNull { el ->
            runCatching {
                json.decodeFromJsonElement(TaskEventDto.serializer(), el)
            }.getOrNull()
        }.sortedBy { it.seq }
    }

    private fun parseDownloadFilename(contentDisposition: String?): String? {
        if (contentDisposition.isNullOrBlank()) return null
        val key = "filename=\""
        val idx = contentDisposition.indexOf(key, ignoreCase = true)
        if (idx < 0) return null
        return contentDisposition
            .substring(idx + key.length)
            .substringBefore('"')
            .trim()
            .takeIf { it.isNotEmpty() }
    }
}

data class TaskSummaryDto(
    val taskId: String,
    val projectId: String?,
    val prompt: String?,
    val status: String,
    val assistant: String? = null,
    val agentProfile: String? = null,
)

data class ProjectSummaryDto(
    val projectId: String,
    val name: String? = null,
    val roleName: String? = null,
)

data class AgentNodeDto(
    val nodeId: String,
    val version: String? = null,
    val capabilities: String? = null,
    val lastHeartbeatAt: String? = null,
    val online: Boolean = false,
)

data class ArtifactListItem(
    val artifactId: String,
    val taskId: String,
    val name: String?,
    val contentType: String?,
    val sizeBytes: Long?,
    val sha256: String?,
)

data class ArtifactDownloadData(
    val bytes: ByteArray,
    val contentType: String?,
    val fileName: String?,
)
