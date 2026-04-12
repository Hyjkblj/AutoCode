package com.autocode.mobile.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.time.Instant
import java.util.concurrent.TimeUnit

/**
 * Minimal control-plane HTTP client for mobile app flows.
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
                val body =
                    buildJsonObject {
                        put("username", username.trim())
                        put("password", password)
                    }.toString()
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/auth/login"))
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(200)}")
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
        agentProfile: String,
    ): Result<TaskSummaryDto> =
        withContext(Dispatchers.IO) {
            runCatching {
                val body =
                    buildJsonObject {
                        put("projectId", projectId.trim())
                        put("prompt", prompt.trim())
                        put("assistant", assistant.trim())
                        put("agentProfile", agentProfile.trim())
                        put("inputMode", "voice_text")
                        put("riskPolicy", "strict_approval")
                    }.toString()
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/tasks"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
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
    ): Result<TaskSummaryDto> {
        val prompt = buildDeployPrompt(artifactId, environment, versionLabel, sourceTaskId)
        return createTask(
            baseUrl = baseUrl,
            bearerToken = bearerToken,
            projectId = projectId,
            prompt = prompt,
            assistant = "deployer",
            agentProfile = "deployer",
        )
    }

    suspend fun listTasks(
        baseUrl: String,
        bearerToken: String,
        projectId: String?,
        assistant: String?,
    ): Result<List<TaskSummaryDto>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val url =
                    buildUrl(
                        baseUrl = baseUrl,
                        path = "/api/v1/tasks",
                        query =
                            linkedMapOf(
                                "projectId" to projectId,
                                "assistant" to assistant,
                            ),
                    )
                val req =
                    Request.Builder()
                        .url(url)
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    // Older control-plane versions do not have list endpoint yet.
                    if (resp.code == 404 || resp.code == 405) return@runCatching emptyList()
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
                    parseTaskSummaryListEnvelope(text)
                }
            }
        }

    suspend fun listProjects(
        baseUrl: String,
        bearerToken: String,
    ): Result<List<ProjectSummaryDto>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/projects"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
                    parseProjectSummaryListEnvelope(text)
                }
            }
        }

    suspend fun listAgentNodes(
        baseUrl: String,
        bearerToken: String,
    ): Result<List<AgentNodeDto>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/agent/nodes"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
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
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/tasks/${taskId.trim()}/artifacts"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
                    parseGatewayArtifactList(text, taskId.trim())
                }
            }
        }

    suspend fun resolveArtifactSiteUrl(
        baseUrl: String,
        bearerToken: String,
        taskId: String,
        artifactId: String,
    ): Result<ArtifactSiteUrlData> =
        withContext(Dispatchers.IO) {
            runCatching {
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/tasks/${taskId.trim()}/artifacts/${artifactId.trim()}/site-url"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) error("artifact not found (404)")
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
                    parseArtifactSiteUrlEnvelope(text)
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
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/tasks/${taskId.trim()}/artifacts/${artifactId.trim()}/download"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val bytes = resp.body?.bytes() ?: ByteArray(0)
                    if (resp.code == 404) error("artifact not found (404)")
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
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/tasks/${taskId.trim()}"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) error("task not found (404)")
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
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
                val req =
                    Request.Builder()
                        .url(
                            buildUrl(
                                baseUrl = baseUrl,
                                path = "/api/v1/tasks/${taskId.trim()}/events",
                                query = mapOf("lastSeq" to maxOf(0L, lastSeq).toString()),
                            ),
                        )
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .get()
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) error("task not found (404)")
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
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
                val body =
                    buildJsonObject {
                        put("approvalId", approvalId.trim())
                        put("decision", decision.trim())
                        comment?.trim()?.takeIf { it.isNotEmpty() }?.let { put("comment", it) }
                    }.toString()
                val req =
                    Request.Builder()
                        .url(buildUrl(baseUrl, "/api/v1/tasks/${taskId.trim()}/approval"))
                        .header("Authorization", "Bearer ${bearerToken.trim()}")
                        .post(body.toRequestBody(mediaJson))
                        .build()
                client.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.code == 404) error("approval or task not found (404)")
                    if (!resp.isSuccessful) error("HTTP ${resp.code}: ${text.take(300)}")
                    parseTaskSummaryEnvelope(text)
                }
            }
        }

    private fun buildUrl(baseUrl: String, path: String, query: Map<String, String?> = emptyMap()): String {
        val raw = "${normalizeBaseUrl(baseUrl)}$path"
        val base = raw.toHttpUrlOrNull() ?: error("invalid URL: $raw")
        val builder = base.newBuilder()
        query.forEach { (k, v) ->
            v?.trim()?.takeIf { it.isNotEmpty() }?.let { builder.addQueryParameter(k, it) }
        }
        return builder.build().toString()
    }

    private fun buildDeployPrompt(
        artifactId: String?,
        environment: String,
        versionLabel: String,
        sourceTaskId: String?,
    ): String {
        val normalizedArtifact = artifactId?.trim().takeUnless { it.isNullOrEmpty() } ?: "unknown-artifact"
        val normalizedEnv = environment.trim().ifEmpty { "staging" }
        val normalizedVersion = versionLabel.trim().ifEmpty { "v-${System.currentTimeMillis()}" }
        val normalizedSource = sourceTaskId?.trim().takeUnless { it.isNullOrEmpty() }
        return if (normalizedSource == null) {
            "Deploy artifact $normalizedArtifact to $normalizedEnv with version $normalizedVersion"
        } else {
            "Deploy artifact $normalizedArtifact to $normalizedEnv with version $normalizedVersion (sourceTaskId=$normalizedSource)"
        }
    }

    private fun parseAccessToken(responseBody: String): String {
        val payload = parseEnvelopePayload(responseBody).jsonObjectOrNull()
            ?: error("login response missing payload")
        val token = stringValue(payload, "accessToken")
        if (token.isNullOrBlank()) error("login response missing accessToken")
        return token
    }

    private fun parseTaskSummaryEnvelope(responseBody: String): TaskSummaryDto {
        val payload = parseEnvelopePayload(responseBody).jsonObjectOrNull()
            ?: error("response payload is not an object")
        return parseTaskSummary(payload)
    }

    private fun parseTaskSummaryListEnvelope(responseBody: String): List<TaskSummaryDto> =
        parseTaskSummaryList(parseEnvelopePayload(responseBody))

    private fun parseTaskSummaryList(payload: JsonElement): List<TaskSummaryDto> =
        payloadToObjectArray(payload, "items", "tasks", "content")
            .mapNotNull { o ->
                runCatching { parseTaskSummary(o) }.getOrNull()
            }

    private fun parseProjectSummaryListEnvelope(responseBody: String): List<ProjectSummaryDto> =
        payloadToObjectArray(parseEnvelopePayload(responseBody), "items", "projects", "content")
            .mapNotNull { o ->
                val projectId = stringValue(o, "projectId", "id") ?: return@mapNotNull null
                ProjectSummaryDto(
                    projectId = projectId,
                    name = stringValue(o, "name", "projectName"),
                    roleName = stringValue(o, "roleName", "role"),
                )
            }

    private fun parseAgentNodeListEnvelope(responseBody: String): List<AgentNodeDto> =
        payloadToObjectArray(parseEnvelopePayload(responseBody), "items", "nodes", "content")
            .mapNotNull { o ->
                val nodeId = stringValue(o, "nodeId", "id") ?: return@mapNotNull null
                AgentNodeDto(
                    nodeId = nodeId,
                    version = stringValue(o, "version"),
                    capabilities = stringValue(o, "capabilities"),
                    lastHeartbeatAt = stringValue(o, "lastHeartbeatAt", "lastHeartbeat", "heartbeatAt"),
                    online = booleanValue(o, "online", "isOnline", "alive") ?: false,
                )
            }

    private fun parseTaskSummary(o: JsonObject): TaskSummaryDto {
        val taskId = stringValue(o, "taskId", "id") ?: error("task summary missing taskId")
        return TaskSummaryDto(
            taskId = taskId,
            projectId = stringValue(o, "projectId"),
            prompt = stringValue(o, "prompt"),
            status = stringValue(o, "status") ?: "UNKNOWN",
            assistant = stringValue(o, "assistant"),
            agentProfile = stringValue(o, "agentProfile"),
            createdAtMillis = epochMillisValue(o, "createdAtMillis", "createdAt"),
            updatedAtMillis = epochMillisValue(o, "updatedAtMillis", "updatedAt"),
        )
    }

    private fun parseGatewayArtifactList(body: String, fallbackTaskId: String): List<ArtifactListItem> {
        val payload = parseEnvelopePayload(body).jsonObjectOrNull() ?: return emptyList()
        val taskId = stringValue(payload, "taskId") ?: fallbackTaskId
        val items = payload["items"] as? JsonArray ?: return emptyList()
        return items.mapNotNull { el ->
            val o = el.jsonObjectOrNull() ?: return@mapNotNull null
            ArtifactListItem(
                artifactId = stringValue(o, "artifactId").orEmpty(),
                taskId = stringValue(o, "taskId") ?: taskId,
                name = stringValue(o, "name", "fileName"),
                contentType = stringValue(o, "contentType", "mimeType"),
                sizeBytes = longValue(o, "sizeBytes", "size"),
                sha256 = stringValue(o, "sha256"),
            )
        }
    }

    private fun parseArtifactSiteUrlEnvelope(body: String): ArtifactSiteUrlData {
        val payload = parseEnvelopePayload(body).jsonObjectOrNull()
            ?: error("site-url response payload is not an object")
        val shortUrl = stringValue(payload, "shortUrl")
        val url = shortUrl ?: stringValue(payload, "shareUrl", "url")
            ?: error("site-url response missing url")
        return ArtifactSiteUrlData(
            url = url,
            canonicalUrl = stringValue(payload, "url"),
            shareUrl = stringValue(payload, "shareUrl"),
            shortUrl = shortUrl,
            entryPath = stringValue(payload, "entryPath"),
            tokenized = booleanValue(payload, "tokenized", "shared") ?: false,
        )
    }

    private fun parseTaskEventsEnvelope(responseBody: String): List<TaskEventDto> {
        val payload = parseEnvelopePayload(responseBody)
        val array =
            when (payload) {
                is JsonArray -> payload
                is JsonObject -> {
                    (payload["items"] as? JsonArray)
                        ?: (payload["events"] as? JsonArray)
                        ?: JsonArray(emptyList())
                }
                else -> JsonArray(emptyList())
            }
        return array.mapNotNull { el ->
            runCatching { json.decodeFromJsonElement(TaskEventDto.serializer(), el) }.getOrNull()
        }.sortedBy { it.seq }
    }

    private fun parseEnvelopePayload(responseBody: String): JsonElement {
        val obj = json.parseToJsonElement(responseBody).jsonObject
        if (obj["ok"]?.jsonPrimitive?.booleanOrNull != true) {
            val err = obj["error"]?.jsonPrimitive?.contentOrNull ?: "request failed"
            error(err)
        }
        return obj["payload"] ?: JsonNull
    }

    private fun payloadToObjectArray(payload: JsonElement, vararg keys: String): List<JsonObject> =
        when (payload) {
            is JsonArray -> payload.mapNotNull { it.jsonObjectOrNull() }
            is JsonObject -> {
                val nested =
                    keys
                        .asSequence()
                        .mapNotNull { key -> payload[key] as? JsonArray }
                        .firstOrNull()
                if (nested != null) {
                    nested.mapNotNull { it.jsonObjectOrNull() }
                } else if (stringValue(payload, "taskId", "projectId", "nodeId") != null) {
                    listOf(payload)
                } else {
                    emptyList()
                }
            }
            else -> emptyList()
        }

    private fun stringValue(obj: JsonObject, vararg keys: String): String? {
        for (key in keys) {
            val value = obj[key] ?: continue
            when (value) {
                is JsonPrimitive -> {
                    val text = value.contentOrNull?.trim().orEmpty()
                    if (text.isNotEmpty()) return text
                }
                else -> {
                    val text = value.toString().trim()
                    if (text.isNotEmpty() && text != "null") return text
                }
            }
        }
        return null
    }

    private fun booleanValue(obj: JsonObject, vararg keys: String): Boolean? {
        for (key in keys) {
            val primitive = obj[key] as? JsonPrimitive ?: continue
            primitive.booleanOrNull?.let { return it }
            when (primitive.contentOrNull?.trim()?.lowercase()) {
                "true", "1", "yes", "y", "online" -> return true
                "false", "0", "no", "n", "offline" -> return false
            }
        }
        return null
    }

    private fun longValue(obj: JsonObject, vararg keys: String): Long? {
        for (key in keys) {
            val primitive = obj[key] as? JsonPrimitive ?: continue
            primitive.longOrNull?.let { return it }
            primitive.doubleOrNull?.let { return it.toLong() }
            primitive.contentOrNull?.trim()?.toLongOrNull()?.let { return it }
        }
        return null
    }

    private fun epochMillisValue(obj: JsonObject, vararg keys: String): Long? {
        for (key in keys) {
            val primitive = obj[key] as? JsonPrimitive ?: continue
            primitive.longOrNull?.let { return it }
            primitive.doubleOrNull?.let { return it.toLong() }
            val raw = primitive.contentOrNull?.trim().orEmpty()
            if (raw.isEmpty()) continue
            raw.toLongOrNull()?.let { return it }
            raw.toDoubleOrNull()?.toLong()?.let { return it }
            runCatching { Instant.parse(raw).toEpochMilli() }.getOrNull()?.let { return it }
        }
        return null
    }

    private fun JsonElement.jsonObjectOrNull(): JsonObject? = this as? JsonObject

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
    val createdAtMillis: Long? = null,
    val updatedAtMillis: Long? = null,
)

data class ProjectSummaryDto(
    val projectId: String,
    val name: String?,
    val roleName: String?,
)

data class AgentNodeDto(
    val nodeId: String,
    val version: String?,
    val capabilities: String?,
    val lastHeartbeatAt: String?,
    val online: Boolean,
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

data class ArtifactSiteUrlData(
    val url: String,
    val canonicalUrl: String?,
    val shareUrl: String?,
    val shortUrl: String?,
    val entryPath: String?,
    val tokenized: Boolean,
)
