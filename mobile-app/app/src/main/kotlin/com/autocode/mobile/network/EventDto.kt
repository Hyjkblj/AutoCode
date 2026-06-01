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

// ── Super-Individual event type constants ──────────────────────────

const val CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
const val CLARIFICATION_ANSWERED = "CLARIFICATION_ANSWERED"
const val REPO_BOOTSTRAP_STARTED = "REPO_BOOTSTRAP_STARTED"
const val REPO_BOOTSTRAP_DONE = "REPO_BOOTSTRAP_DONE"
const val CODE_INDEX_BUILT = "CODE_INDEX_BUILT"
const val PLAN_APPROVAL_REQUESTED = "PLAN_APPROVAL_REQUESTED"
const val TEST_GENERATED = "TEST_GENERATED"
const val KNOWLEDGE_WRITEBACK = "KNOWLEDGE_WRITEBACK"

