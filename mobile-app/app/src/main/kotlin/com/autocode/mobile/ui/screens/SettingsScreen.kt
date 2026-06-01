package com.autocode.mobile.ui.screens

import android.Manifest
import android.os.Build
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.AgentProfile
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.GenerationTarget
import com.autocode.mobile.displayLabel
import com.autocode.mobile.ui.components.MobileUiTestTags
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
internal fun AccountTab(vm: AppViewModel) {
    val state by vm.uiState.collectAsStateWithLifecycle()
    val notificationPermissionState = rememberPermissionState(Manifest.permission.POST_NOTIFICATIONS)
    val canPostNotifications =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || notificationPermissionState.status.isGranted
    var baseUrlDraft by rememberSaveable { mutableStateOf(state.baseUrl) }
    var targetDraft by rememberSaveable { mutableStateOf(state.generationTarget.name) }
    var profileDraft by rememberSaveable { mutableStateOf(state.agentProfile.name) }
    LaunchedEffect(state.baseUrl, state.generationTarget, state.agentProfile) {
        baseUrlDraft = state.baseUrl
        targetDraft = state.generationTarget.name
        profileDraft = state.agentProfile.name
    }
    LaunchedEffect(state.baseUrl, state.session?.accessToken) {
        vm.refreshAgentNodes()
    }
    Column(
        Modifier
            .padding(20.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text("我的", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        Text("连接与生成设置", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = baseUrlDraft,
            onValueChange = { baseUrlDraft = it },
            label = { Text("控制面地址") },
            placeholder = { Text("留空=离线；模拟器访问本机可用 http://10.0.2.2:8058") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2,
        )
        Spacer(Modifier.height(12.dp))
        Text("生成目标", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        RowOfTargetChips(
            selected = targetDraft,
            onSelect = { targetDraft = it },
        )
        Spacer(Modifier.height(12.dp))
        Text("代理身份", style = MaterialTheme.typography.labelLarge)
        Spacer(Modifier.height(8.dp))
        RowOfAgentProfileChips(
            selected = profileDraft,
            onSelect = { profileDraft = it },
        )
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                val t =
                    when (targetDraft) {
                        GenerationTarget.WECHAT_MINI_PROGRAM.name -> GenerationTarget.WECHAT_MINI_PROGRAM
                        else -> GenerationTarget.WEB
                    }
                val p =
                    when (profileDraft) {
                        AgentProfile.AI_AGENT.name -> AgentProfile.AI_AGENT
                        else -> AgentProfile.CODER
                    }
                vm.saveConnectivitySettings(baseUrlDraft, t, p)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("保存连接设置")
        }
        Spacer(Modifier.height(24.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.fillMaxWidth(0.8f)) {
                        Text("任务通知", style = MaterialTheme.typography.titleSmall)
                        Text(
                            text =
                                if (state.notificationsEnabled) {
                                    "审批待处理、任务完成、任务失败时推送通知。"
                                } else {
                                    "通知已关闭。"
                                },
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Switch(
                        modifier = Modifier.testTag(MobileUiTestTags.NOTIFICATION_SWITCH),
                        checked = state.notificationsEnabled,
                        onCheckedChange = { enabled ->
                            vm.setNotificationsEnabled(enabled)
                            if (
                                enabled &&
                                Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                                !notificationPermissionState.status.isGranted
                            ) {
                                notificationPermissionState.launchPermissionRequest()
                            }
                        },
                    )
                }
                if (state.notificationsEnabled && !canPostNotifications) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = "Android 13+ 需要授予通知权限。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("显示名", style = MaterialTheme.typography.labelMedium)
                Text(state.session?.displayName ?: "—")
                Spacer(Modifier.height(12.dp))
                Text("访问令牌（仅展示）", style = MaterialTheme.typography.labelMedium)
                Text(
                    state.session?.accessToken ?: "—",
                    fontFamily = FontFamily.Monospace,
                    maxLines = 1,
                )
            }
        }
        Spacer(Modifier.height(24.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("代理节点", style = MaterialTheme.typography.titleMedium)
            TextButton(
                onClick = { vm.refreshAgentNodes() },
                enabled = !state.isRefreshingAgentNodes,
            ) {
                Text(if (state.isRefreshingAgentNodes) "刷新中..." else "刷新")
            }
        }
        if (state.baseUrl.isBlank() || state.session == null) {
            Text(
                "请先配置控制面地址并登录后查看节点能力。",
                style = MaterialTheme.typography.bodySmall,
            )
        } else if (state.agentNodes.isEmpty() && state.isRefreshingAgentNodes) {
            Spacer(Modifier.height(8.dp))
            CircularProgressIndicator()
        } else if (state.agentNodes.isEmpty()) {
            Text(
                "暂无代理节点上报。",
                style = MaterialTheme.typography.bodySmall,
            )
        } else {
            Spacer(Modifier.height(8.dp))
            state.agentNodes.forEach { node ->
                Card(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(node.nodeId, style = MaterialTheme.typography.titleSmall)
                            Text(
                                if (node.online) "在线" else "离线",
                                color =
                                    if (node.online) Color(0xFF2E7D32)
                                    else MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                        node.version?.takeIf { it.isNotBlank() }?.let {
                            Spacer(Modifier.height(4.dp))
                            Text("版本：$it", style = MaterialTheme.typography.bodySmall)
                        }
                        node.lastHeartbeatAt?.takeIf { it.isNotBlank() }?.let {
                            Spacer(Modifier.height(4.dp))
                            Text("心跳时间：$it", style = MaterialTheme.typography.bodySmall)
                        }
                        val capabilities = node.capabilities?.trim().orEmpty()
                        if (capabilities.isNotEmpty()) {
                            Spacer(Modifier.height(6.dp))
                            Text("能力说明", style = MaterialTheme.typography.labelMedium)
                            Text(
                                text = capabilities,
                                fontFamily = FontFamily.Monospace,
                                style = MaterialTheme.typography.bodySmall,
                                maxLines = 6,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = { vm.logout() }) {
            Text("退出登录", color = MaterialTheme.colorScheme.error)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RowOfTargetChips(
    selected: String,
    onSelect: (String) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(
            selected = selected == GenerationTarget.WEB.name,
            onClick = { onSelect(GenerationTarget.WEB.name) },
            label = { Text(GenerationTarget.WEB.displayLabel()) },
        )
        FilterChip(
            selected = selected == GenerationTarget.WECHAT_MINI_PROGRAM.name,
            onClick = { onSelect(GenerationTarget.WECHAT_MINI_PROGRAM.name) },
            label = { Text(GenerationTarget.WECHAT_MINI_PROGRAM.displayLabel()) },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RowOfAgentProfileChips(
    selected: String,
    onSelect: (String) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(
            selected = selected == AgentProfile.CODER.name,
            onClick = { onSelect(AgentProfile.CODER.name) },
            label = { Text(AgentProfile.CODER.displayLabel()) },
        )
        FilterChip(
            selected = selected == AgentProfile.AI_AGENT.name,
            onClick = { onSelect(AgentProfile.AI_AGENT.name) },
            label = { Text(AgentProfile.AI_AGENT.displayLabel()) },
        )
    }
}
