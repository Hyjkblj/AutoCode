package com.autocode.mobile.ui.screens

import android.Manifest
import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.*
import com.autocode.mobile.ui.components.MobileUiTestTags
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
internal fun SettingsScreen(vm: AppViewModel) {
    val uiState by vm.uiState.collectAsStateWithLifecycle()
    val notificationPermissionState = rememberPermissionState(Manifest.permission.POST_NOTIFICATIONS)
    val canPostNotifications =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || notificationPermissionState.status.isGranted

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Header
        Text(
            text = "设置",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )

        // Profile Card
        ProfileCard(
            name = uiState.session?.displayName ?: "未登录",
            email = "user@autocode.dev"
        )

        // Account Bindings
        AccountBindingsCard()

        // Appearance
        AppearanceCard()

        // Agent Configuration
        AgentConfigCard(vm = vm, uiState = uiState)

        // Notifications
        NotificationsCard(
            vm = vm,
            uiState = uiState,
            canPostNotifications = canPostNotifications,
            notificationPermissionState = notificationPermissionState
        )

        // System Info
        SystemInfoCard()

        // Logout & Switch Account
        if (uiState.session != null) {
            OutlinedButton(
                onClick = { vm.logout() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MaterialTheme.colorScheme.error
                )
            ) {
                Icon(Icons.Outlined.Logout, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("退出登录")
            }
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = { vm.switchAccount() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.SwitchAccount, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("切换账号")
            }
        }

        // Bottom spacing
        Spacer(modifier = Modifier.height(80.dp))
    }
}

@Composable
private fun ProfileCard(name: String, email: String) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Filled.Person,
                    contentDescription = null,
                    modifier = Modifier.size(24.dp),
                    tint = MaterialTheme.colorScheme.onPrimaryContainer
                )
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = email,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun AccountBindingsCard() {
    val bindings = listOf(
        Triple(Icons.Outlined.Code, "GitHub", false),
        Triple(Icons.Outlined.Email, "Google", false),
        Triple(Icons.Outlined.Chat, "Slack", false),
    )

    SettingsSection(title = "账户绑定", icon = Icons.Outlined.Link) {
        bindings.forEach { (icon, name, connected) ->
            SettingsRow(
                icon = icon,
                title = name,
                subtitle = if (connected) "已连接" else "未连接",
                trailing = {
                    TextButton(onClick = { /* TODO */ }) {
                        Text(if (connected) "断开" else "连接")
                    }
                }
            )
        }
    }
}

@Composable
private fun AppearanceCard() {
    var selectedTheme by remember { mutableStateOf("system") }

    SettingsSection(title = "外观", icon = Icons.Outlined.Palette) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            listOf("light" to "浅色", "dark" to "深色", "system" to "跟随系统").forEach { (value, label) ->
                FilterChip(
                    selected = selectedTheme == value,
                    onClick = { selectedTheme = value },
                    label = { Text(label) },
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AgentConfigCard(vm: AppViewModel, uiState: UiState) {
    var baseUrlDraft by rememberSaveable { mutableStateOf(uiState.baseUrl) }
    var targetDraft by rememberSaveable { mutableStateOf(uiState.generationTarget.name) }
    var profileDraft by rememberSaveable { mutableStateOf(uiState.agentProfile.name) }

    LaunchedEffect(uiState.baseUrl, uiState.generationTarget, uiState.agentProfile) {
        baseUrlDraft = uiState.baseUrl
        targetDraft = uiState.generationTarget.name
        profileDraft = uiState.agentProfile.name
    }

    SettingsSection(title = "Agent 配置", icon = Icons.Outlined.SmartToy) {
        // Base URL
        OutlinedTextField(
            value = baseUrlDraft,
            onValueChange = { baseUrlDraft = it },
            label = { Text("服务地址") },
            placeholder = { Text("留空=离线；模拟器访问本机可用 http://10.0.2.2:8058") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2,
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Generation Target
        Text(
            text = "生成目标",
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(vertical = 8.dp)
        )
        RowOfTargetChips(
            selected = targetDraft,
            onSelect = { targetDraft = it },
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Agent Profile
        Text(
            text = "Agent 模式",
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(vertical = 8.dp)
        )
        RowOfAgentProfileChips(
            selected = profileDraft,
            onSelect = { profileDraft = it },
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Save button
        Button(
            onClick = {
                val t = when (targetDraft) {
                    GenerationTarget.WECHAT_MINI_PROGRAM.name -> GenerationTarget.WECHAT_MINI_PROGRAM
                    else -> GenerationTarget.WEB
                }
                val p = when (profileDraft) {
                    AgentProfile.AI_AGENT.name -> AgentProfile.AI_AGENT
                    else -> AgentProfile.CODER
                }
                vm.saveConnectivitySettings(baseUrlDraft, t, p)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("保存连接设置")
        }
    }
}

@OptIn(ExperimentalPermissionsApi::class)
@Composable
private fun NotificationsCard(
    vm: AppViewModel,
    uiState: UiState,
    canPostNotifications: Boolean,
    notificationPermissionState: com.google.accompanist.permissions.PermissionState
) {
    SettingsSection(title = "通知", icon = Icons.Outlined.Notifications) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text("推送通知", style = MaterialTheme.typography.bodyMedium)
                Text(
                    "接收任务状态和审批提醒",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Switch(
                modifier = Modifier.testTag(MobileUiTestTags.NOTIFICATION_SWITCH),
                checked = uiState.notificationsEnabled,
                onCheckedChange = { enabled ->
                    vm.setNotificationsEnabled(enabled)
                    if (
                        enabled &&
                        Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                        !notificationPermissionState.status.isGranted
                    ) {
                        notificationPermissionState.launchPermissionRequest()
                    }
                }
            )
        }
        if (uiState.notificationsEnabled && !canPostNotifications) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Android 13+ 需要授予通知权限。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
    }
}

@Composable
private fun SystemInfoCard() {
    SettingsSection(title = "系统信息", icon = Icons.Outlined.Info) {
        SettingsRow(icon = Icons.Outlined.Code, title = "版本", subtitle = "2.0.0")
        SettingsRow(icon = Icons.Outlined.Build, title = "构建", subtitle = "2026.05.27")
    }
}

// -- Reusable building blocks --

@Composable
private fun SettingsSection(
    title: String,
    icon: ImageVector,
    content: @Composable ColumnScope.() -> Unit
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.primary
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            content()
        }
    }
}

@Composable
private fun SettingsRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    trailing: @Composable (() -> Unit)? = null
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(18.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(text = title, style = MaterialTheme.typography.bodyMedium)
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        trailing?.invoke()
    }
}

// -- Chip composables (kept from original AccountTab) --

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
