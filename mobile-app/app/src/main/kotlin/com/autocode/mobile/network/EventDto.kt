package com.autocode.mobile.network

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class TaskEventDto(
    val eventId: String? = null,
    val taskId: String? = null,
    val type: String? = null,
    val payload: JsonObject = JsonObject(emptyMap()),
    val seq: Long = 0L,
    val timestamp: String? = null,
    val eventVersion: Int = 1,
)

