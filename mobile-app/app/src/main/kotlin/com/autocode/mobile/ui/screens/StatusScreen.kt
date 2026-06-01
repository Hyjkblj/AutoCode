package com.autocode.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.autocode.mobile.AppViewModel
import com.autocode.mobile.TaskItem
import com.autocode.mobile.TaskStatus
import com.autocode.mobile.ui.components.*

@Composable
fun StatusScreen(vm: AppViewModel) {
    val uiState by vm.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "状态监控",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f)
            )
            SystemStatusBadge(isHealthy = true)
        }

        // Active Tasks
        ActiveTasksCard(tasks = uiState.tasks.filter {
            it.status == TaskStatus.RUNNING || it.status == TaskStatus.QUEUED
        })

        // Statistics
        StatsRow(successRate = 87, avgTimeMinutes = 2.4)

        // Resource Utilization
        ResourceUtilizationCard(cpuPercent = 34, memPercent = 62, diskPercent = 45)

        // Service Health
        ServiceHealthCard()

        // Bottom spacing for nav bar
        Spacer(modifier = Modifier.height(80.dp))
    }
}

@Composable
private fun SystemStatusBadge(isHealthy: Boolean) {
    Surface(
        shape = RoundedCornerShape(20.dp),
        color = if (isHealthy) Color(0xFF22C55E).copy(alpha = 0.1f) else MaterialTheme.colorScheme.errorContainer
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(if (isHealthy) Color(0xFF22C55E) else MaterialTheme.colorScheme.error)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = if (isHealthy) "系统正常" else "异常",
                style = MaterialTheme.typography.labelMedium,
                color = if (isHealthy) Color(0xFF22C55E) else MaterialTheme.colorScheme.error
            )
        }
    }
}

@Composable
private fun ActiveTasksCard(tasks: List<TaskItem>) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.PendingActions,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.primaryContainer
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "活跃任务",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.weight(1f))
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.2f)
                ) {
                    Text(
                        text = tasks.size.toString(),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            if (tasks.isEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "暂无活跃任务",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.Center
                )
            } else {
                Spacer(modifier = Modifier.height(12.dp))
                tasks.forEach { task ->
                    ActiveTaskRow(task)
                    if (task != tasks.last()) {
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ActiveTaskRow(task: TaskItem) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = task.prompt.take(20) + if (task.prompt.length > 20) "..." else "",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    text = when (task.status) {
                        TaskStatus.RUNNING -> "运行中"
                        TaskStatus.QUEUED -> "队列中"
                        else -> task.status.name
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { (task.progress.coerceIn(0, 100)) / 100f },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp)
                    .clip(RoundedCornerShape(3.dp)),
                color = MaterialTheme.colorScheme.primaryContainer,
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
            )
        }
    }
}

@Composable
private fun StatsRow(successRate: Int, avgTimeMinutes: Double) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        StatCard(
            value = "${successRate}%",
            label = "成功率",
            trend = "+5%",
            trendUp = true,
            modifier = Modifier.weight(1f)
        )
        StatCard(
            value = "${avgTimeMinutes}m",
            label = "平均执行时间",
            trend = "-12s",
            trendUp = false,
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun StatCard(
    value: String,
    label: String,
    trend: String,
    trendUp: Boolean,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = value,
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (trendUp) Icons.Filled.TrendingUp else Icons.Filled.TrendingDown,
                    contentDescription = null,
                    modifier = Modifier.size(14.dp),
                    tint = Color(0xFF22C55E)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = trend,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF22C55E)
                )
            }
        }
    }
}

@Composable
private fun ResourceUtilizationCard(cpuPercent: Int, memPercent: Int, diskPercent: Int) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.Memory,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.tertiary
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "资源使用",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }
            Spacer(modifier = Modifier.height(16.dp))
            ResourceBar(label = "CPU", percent = cpuPercent, color = MaterialTheme.colorScheme.tertiary)
            Spacer(modifier = Modifier.height(12.dp))
            ResourceBar(label = "内存", percent = memPercent, color = MaterialTheme.colorScheme.primaryContainer)
            Spacer(modifier = Modifier.height(12.dp))
            ResourceBar(label = "磁盘", percent = diskPercent, color = Color(0xFF22C55E))
        }
    }
}

@Composable
private fun ResourceBar(label: String, percent: Int, color: Color) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = "${percent}%",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { percent / 100f },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(RoundedCornerShape(4.dp)),
            color = color,
            trackColor = MaterialTheme.colorScheme.surface,
        )
    }
}

@Composable
private fun ServiceHealthCard() {
    val services = listOf(
        "Control Plane" to true,
        "Python Agent" to true,
        "Event Service" to true,
        "Redis" to true,
    )

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.HealthAndSafety,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = Color(0xFF22C55E)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "系统健康",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                services.forEach { (name, healthy) ->
                    ServiceChip(
                        name = name,
                        healthy = healthy,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
}

@Composable
private fun ServiceChip(
    name: String,
    healthy: Boolean,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(if (healthy) Color(0xFF22C55E) else MaterialTheme.colorScheme.error)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = name,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1
            )
        }
    }
}
