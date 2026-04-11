package com.autocode.mobile.network

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlin.math.min

class WebSocketClient {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private val client: OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

    private data class ConnectionConfig(
        val baseUrl: String,
        val bearerToken: String?,
        val taskId: String,
        val onEvent: (TaskEventDto) -> Unit,
        val onDisconnect: (String?) -> Unit,
    )

    private data class StompFrame(
        val command: String,
        val headers: Map<String, String>,
        val body: String,
    )

    private var ws: WebSocket? = null
    private var reconnectJob: Job? = null
    private var config: ConnectionConfig? = null
    private val frameBuffer = StringBuilder()

    @Volatile
    private var manualDisconnect = false

    @Volatile
    private var reconnectAttempt = 0

    @Volatile
    private var stompConnected = false

    @Volatile
    private var lastSeq = 0L

    fun connect(
        baseUrl: String,
        bearerToken: String?,
        taskId: String,
        lastSeq: Long,
        onEvent: (TaskEventDto) -> Unit,
        onDisconnect: (String?) -> Unit,
    ) {
        this.config =
            ConnectionConfig(
                baseUrl = baseUrl.trim(),
                bearerToken = bearerToken?.trim(),
                taskId = taskId.trim(),
                onEvent = onEvent,
                onDisconnect = onDisconnect,
            )
        this.lastSeq = maxOf(0L, lastSeq)
        this.manualDisconnect = false
        this.reconnectAttempt = 0
        this.stompConnected = false
        reconnectJob?.cancel()
        ws?.close(1000, "replace")
        openSocket()
    }

    fun disconnect() {
        manualDisconnect = true
        reconnectJob?.cancel()
        reconnectJob = null
        ws?.close(1000, "client_close")
        ws = null
        stompConnected = false
        frameBuffer.clear()
    }

    private fun openSocket() {
        val cfg = config ?: return
        val request =
            Request.Builder()
                .url(toWebSocketUrl(cfg.baseUrl))
                .build()
        ws = client.newWebSocket(request, createListener(cfg))
    }

    private fun createListener(cfg: ConnectionConfig): WebSocketListener =
        object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                stompConnected = false
                frameBuffer.clear()
                webSocket.send(
                    buildFrame(
                        command = "CONNECT",
                        headers =
                            buildMap {
                                put("accept-version", "1.2")
                                put("heart-beat", "10000,10000")
                                put("deviceId", "mobile-${UUID.randomUUID()}")
                                put("lastSeq", lastSeq.toString())
                                if (!cfg.bearerToken.isNullOrBlank()) {
                                    put("Authorization", "Bearer ${cfg.bearerToken}")
                                }
                            },
                    ),
                )
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                frameBuffer.append(text)
                drainFrames(cfg, webSocket)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                stompConnected = false
                handleSocketDown(cfg, "closed: $code $reason")
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                val reason =
                    buildString {
                        append(t.message ?: "socket failure")
                        response?.code?.let { code ->
                            append(" (HTTP ").append(code).append(')')
                        }
                    }
                if (isAuthError(reason)) {
                    manualDisconnect = true
                    cfg.onDisconnect(reason)
                    return
                }
                handleSocketDown(cfg, reason)
            }
        }

    private fun drainFrames(cfg: ConnectionConfig, webSocket: WebSocket) {
        while (true) {
            val frameEnd = frameBuffer.indexOf("\u0000")
            if (frameEnd < 0) return
            val raw = frameBuffer.substring(0, frameEnd)
            frameBuffer.delete(0, frameEnd + 1)
            val parsed = parseFrame(raw) ?: continue
            when (parsed.command) {
                "CONNECTED" -> {
                    stompConnected = true
                    reconnectAttempt = 0
                    webSocket.send(
                        buildFrame(
                            command = "SUBSCRIBE",
                            headers =
                                mapOf(
                                    "id" to "task-${cfg.taskId}",
                                    "destination" to "/topic/tasks/${cfg.taskId}",
                                    "ack" to "auto",
                                    "lastSeq" to lastSeq.toString(),
                                ),
                        ),
                    )
                }

                "MESSAGE" -> {
                    runCatching {
                        json.decodeFromString(TaskEventDto.serializer(), parsed.body)
                    }.onSuccess { e ->
                        val seq = e.seq
                        if (seq > 0) {
                            lastSeq = maxOf(lastSeq, seq)
                        }
                        cfg.onEvent(e)
                    }
                }

                "ERROR" -> {
                    val headerReason = parsed.headers["message"]?.takeIf { it.isNotBlank() }
                    val reason =
                        when {
                            !parsed.body.isBlank() && headerReason != null -> "$headerReason: ${parsed.body}"
                            headerReason != null -> headerReason
                            else -> parsed.body.ifBlank { "stomp error" }
                        }
                    cfg.onDisconnect(reason)
                    if (isAuthError(reason)) {
                        manualDisconnect = true
                    } else {
                        scheduleReconnect()
                    }
                }
            }
        }
    }

    private fun handleSocketDown(cfg: ConnectionConfig, reason: String?) {
        if (manualDisconnect) return
        cfg.onDisconnect(reason)
        if (isAuthError(reason)) {
            manualDisconnect = true
            return
        }
        scheduleReconnect()
    }

    private fun isAuthError(reason: String?): Boolean {
        val normalized = reason?.lowercase() ?: return false
        return normalized.contains("invalid jwt") ||
            normalized.contains("missing or invalid authorization") ||
            normalized.contains("missing or invalid token") ||
            normalized.contains("invalid token") ||
            normalized.contains("missing deviceid") ||
            normalized.contains("unauthenticated") ||
            normalized.contains("access denied") ||
            normalized.contains("accessdeniedexception") ||
            normalized.contains("expired") ||
            normalized.contains("failed to send message to messagechannel") ||
            normalized.contains("clientinboundchannel") ||
            normalized.contains("http 401") ||
            normalized.contains("http 403")
    }

    private fun scheduleReconnect() {
        if (manualDisconnect) return
        reconnectJob?.cancel()
        reconnectJob =
            scope.launch {
                reconnectAttempt += 1
                val delaySec = min(30, 1.shl(min(5, reconnectAttempt - 1)))
                delay(delaySec * 1000L)
                if (!manualDisconnect) {
                    openSocket()
                }
            }
    }

    private fun toWebSocketUrl(baseUrl: String): String {
        val trimmed = baseUrl.trim().trimEnd('/')
        return when {
            trimmed.startsWith("https://") -> "wss://${trimmed.removePrefix("https://")}/ws"
            trimmed.startsWith("http://") -> "ws://${trimmed.removePrefix("http://")}/ws"
            trimmed.startsWith("wss://") -> if (trimmed.endsWith("/ws")) trimmed else "$trimmed/ws"
            trimmed.startsWith("ws://") -> if (trimmed.endsWith("/ws")) trimmed else "$trimmed/ws"
            else -> "ws://$trimmed/ws"
        }
    }

    private fun buildFrame(command: String, headers: Map<String, String>, body: String = ""): String {
        val sb = StringBuilder()
        sb.append(command).append('\n')
        headers.forEach { (k, v) ->
            if (v.isNotBlank()) {
                sb.append(k).append(':').append(v).append('\n')
            }
        }
        sb.append('\n')
        if (body.isNotEmpty()) {
            sb.append(body)
        }
        sb.append('\u0000')
        return sb.toString()
    }

    private fun parseFrame(rawFrame: String): StompFrame? {
        val raw = rawFrame.replace("\r", "").trimStart('\n')
        if (raw.isBlank()) return null
        val splitIdx = raw.indexOf("\n\n")
        val head = if (splitIdx >= 0) raw.substring(0, splitIdx) else raw
        val body = if (splitIdx >= 0) raw.substring(splitIdx + 2) else ""
        val lines = head.lines().filter { it.isNotBlank() }
        if (lines.isEmpty()) return null
        val command = lines.first().trim()
        val headers =
            lines
                .drop(1)
                .mapNotNull { line ->
                    val i = line.indexOf(':')
                    if (i <= 0) return@mapNotNull null
                    val key = line.substring(0, i).trim()
                    val value = line.substring(i + 1).trim()
                    key to value
                }.toMap()
        return StompFrame(command = command, headers = headers, body = body)
    }
}
