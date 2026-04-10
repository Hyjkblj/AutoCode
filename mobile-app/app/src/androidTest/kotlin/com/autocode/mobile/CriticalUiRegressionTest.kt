package com.autocode.mobile

import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.assertDoesNotExist
import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.autocode.mobile.network.TaskEventDto
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CriticalUiRegressionTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun voiceInputButton_requestsPermissionOrStartsByState() {
        var startCalls = 0
        var requestCalls = 0

        composeRule.setContent {
            MaterialTheme {
                VoiceInputButton(
                    permissionGranted = false,
                    onStartVoiceInput = { startCalls += 1 },
                    onRequestPermission = { requestCalls += 1 },
                )
            }
        }

        composeRule.onNodeWithTag(MobileUiTestTags.VOICE_INPUT_BUTTON).assertExists().performClick()
        composeRule.runOnIdle {
            assertEquals(0, startCalls)
            assertEquals(1, requestCalls)
        }

        composeRule.setContent {
            MaterialTheme {
                VoiceInputButton(
                    permissionGranted = true,
                    onStartVoiceInput = { startCalls += 1 },
                    onRequestPermission = { requestCalls += 1 },
                )
            }
        }

        composeRule.onNodeWithTag(MobileUiTestTags.VOICE_INPUT_BUTTON).assertExists().performClick()
        composeRule.runOnIdle {
            assertEquals(1, startCalls)
            assertEquals(1, requestCalls)
        }
    }

    @Test
    fun approvalBottomSheet_allowsApproveWithComment() {
        var approvedComment: String? = null
        var rejectCalled = false
        var timeoutCalled = false
        var dismissCalled = false

        composeRule.setContent {
            MaterialTheme {
                ApprovalBottomSheet(
                    approval =
                        ApprovalRequest(
                            approvalId = "ap_001",
                            taskId = "t_001",
                            action = "exec",
                            command = "git push",
                            cwd = "/workspace",
                            riskScore = 0.92,
                            reason = "high risk",
                            timeoutSeconds = 120,
                        ),
                    onApprove = { approvedComment = it },
                    onReject = { rejectCalled = true },
                    onTimeout = { timeoutCalled = true },
                    onDismiss = { dismissCalled = true },
                )
            }
        }

        composeRule.onNodeWithTag(MobileUiTestTags.APPROVAL_SHEET).assertExists()
        composeRule.onNodeWithTag(MobileUiTestTags.APPROVAL_COMMENT_INPUT).performTextInput("looks good")
        composeRule.onNodeWithTag(MobileUiTestTags.APPROVAL_APPROVE_BUTTON).performClick()
        composeRule.runOnIdle {
            assertEquals("looks good", approvedComment)
            assertFalse(rejectCalled)
            assertFalse(timeoutCalled)
            assertFalse(dismissCalled)
        }
    }

    @Test
    fun taskFailedEventCard_showsStructuredFixLoopFields() {
        val payload =
            buildJsonObject {
                put("errorCode", "E_FIX_42")
                put("riskLevel", "HIGH")
                put("fixLoopAttempt", 2)
                put("maxAttempts", 5)
                put("reason", "模型输出不稳定")
                putJsonArray("issues") {
                    add(JsonPrimitive("schema mismatch"))
                    add(JsonPrimitive("retry timeout"))
                }
            }
        val event =
            TaskEventDto(
                eventId = "ev_1",
                taskId = "task_1",
                type = "TASK_FAILED",
                payload = payload,
                seq = 12L,
                timestamp = "2026-04-09T10:00:00Z",
            )

        composeRule.setContent {
            MaterialTheme {
                AgentEventItem(event = event, fallbackLine = "任务失败：模型输出不稳定")
            }
        }

        composeRule.onNodeWithText("任务失败").assertExists()
        composeRule.onNodeWithText("errorCode: E_FIX_42").assertExists()
        composeRule.onNodeWithText("riskLevel: HIGH").assertExists()
        composeRule.onNodeWithText("fixLoop: 2/5").assertExists()
        composeRule.onNodeWithText("- schema mismatch").assertExists()
        composeRule.onNodeWithText("- retry timeout").assertExists()
    }

    @Test
    fun artifactPreviewCard_showsContentAndTruncatedHint() {
        val preview =
            ArtifactPreview(
                title = "README.md",
                contentType = "text/markdown",
                content = "# Demo\nhello world",
                truncated = true,
                byteSize = 20480,
            )

        composeRule.setContent {
            MaterialTheme {
                ArtifactPreviewCard(preview = preview)
            }
        }

        composeRule.onNodeWithTag(MobileUiTestTags.ARTIFACT_PREVIEW_CARD).assertExists()
        composeRule.onNodeWithText("README.md").assertExists()
        composeRule.onNodeWithText("预览内容已截断，请下载完整文件查看。").assertExists()
        composeRule.runOnIdle {
            assertTrue(preview.truncated)
        }
    }

    @Test
    fun toolStartEventCard_toggleExpansionShowsCwd() {
        val payload =
            buildJsonObject {
                put("tool", "shell")
                put("command", "git status --short")
                put("cwd", "/workspace/demo")
            }
        val event =
            TaskEventDto(
                eventId = "ev_tool_start",
                taskId = "task_tool",
                type = "TOOL_START",
                payload = payload,
                seq = 21L,
                timestamp = "2026-04-10T08:00:00Z",
            )

        composeRule.setContent {
            MaterialTheme {
                AgentEventItem(event = event, fallbackLine = "工具调用")
            }
        }

        composeRule.onNodeWithText("工具调用: shell").assertExists()
        composeRule.onNodeWithText("cwd: /workspace/demo").assertDoesNotExist()
        composeRule.onNodeWithText("展开").assertExists().performClick()
        composeRule.onNodeWithText("cwd: /workspace/demo").assertExists()
        composeRule.onNodeWithText("收起").assertExists().performClick()
        composeRule.onNodeWithText("cwd: /workspace/demo").assertDoesNotExist()
    }

    @Test
    fun deployResultEventCard_showsEndpointAndReason() {
        val payload =
            buildJsonObject {
                put("status", "FAILED")
                put("endpointUrl", "https://staging.example.app")
                put("requestId", "req-20260410-01")
                put("reason", "health check timeout")
            }
        val event =
            TaskEventDto(
                eventId = "ev_deploy_result",
                taskId = "task_deploy",
                type = "DEPLOY_RESULT",
                payload = payload,
                seq = 88L,
                timestamp = "2026-04-10T08:30:00Z",
            )

        composeRule.setContent {
            MaterialTheme {
                AgentEventItem(event = event, fallbackLine = "部署结果")
            }
        }

        composeRule.onNodeWithText("Deploy Result").assertExists()
        composeRule.onNodeWithText("Status: FAILED").assertExists()
        composeRule.onNodeWithText("Endpoint: https://staging.example.app").assertExists()
        composeRule.onNodeWithText("Request ID: req-20260410-01").assertExists()
        composeRule.onNodeWithText("Reason: health check timeout").assertExists()
    }

    @Test
    fun filePatchPreviewEvent_showsExpandForLongDiff() {
        val patch = (1..240).joinToString(separator = "\n") { "+line $it" }
        val payload =
            buildJsonObject {
                put("patch", patch)
            }
        val event =
            TaskEventDto(
                eventId = "ev_patch_preview",
                taskId = "task_patch",
                type = "FILE_PATCH_PREVIEW",
                payload = payload,
                seq = 55L,
                timestamp = "2026-04-10T09:00:00Z",
            )

        composeRule.setContent {
            MaterialTheme {
                AgentEventItem(event = event, fallbackLine = "代码变更预览")
            }
        }

        composeRule.onNodeWithText("代码变更预览").assertExists()
        composeRule.onNodeWithText("展开完整 diff").assertExists().performClick()
        composeRule.onNodeWithText("收起完整 diff").assertExists()
    }
}

