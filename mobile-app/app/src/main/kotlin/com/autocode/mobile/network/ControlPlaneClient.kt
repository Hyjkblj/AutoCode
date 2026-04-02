package com.autocode.mobile.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * 最小控制面 HTTP 客户端（PR-2：创建任务 + 轮询任务摘要）。
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
        )
    }
}

data class TaskSummaryDto(
    val taskId: String,
    val projectId: String?,
    val prompt: String?,
    val status: String,
)
