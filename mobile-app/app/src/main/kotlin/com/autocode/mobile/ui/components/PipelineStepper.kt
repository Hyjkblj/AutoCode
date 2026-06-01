package com.autocode.mobile.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlin.time.Duration

enum class PipelineStage {
    BOOTSTRAP, INDEX, CLARIFY, INTENT, PLAN, CODE, REVIEW, TEST, KNOWLEDGE
}

enum class StageStatus {
    COMPLETED, ACTIVE, SKIPPED, PENDING, FAILED
}

data class PipelineStageInfo(
    val stage: PipelineStage,
    val label: String,
    val status: StageStatus,
    val duration: Duration? = null,
    val detail: String? = null,
)

@Composable
fun PipelineStepper(
    stages: List<PipelineStageInfo>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        stages.forEachIndexed { index, stageInfo ->
            PipelineStep(
                stageInfo = stageInfo,
                isLast = index == stages.lastIndex
            )
        }
    }
}

@Composable
private fun PipelineStep(
    stageInfo: PipelineStageInfo,
    isLast: Boolean
) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.4f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseAlpha"
    )

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top
    ) {
        // Icon column with connecting line
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.width(32.dp)
        ) {
            // Status icon
            Box(
                modifier = Modifier
                    .size(24.dp)
                    .then(
                        if (stageInfo.status == StageStatus.ACTIVE)
                            Modifier.alpha(pulseAlpha)
                        else Modifier
                    ),
                contentAlignment = Alignment.Center
            ) {
                when (stageInfo.status) {
                    StageStatus.COMPLETED -> {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .clip(CircleShape)
                                .background(Color(0xFF22C55E).copy(alpha = 0.2f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Filled.Check,
                                contentDescription = "Completed",
                                modifier = Modifier.size(14.dp),
                                tint = Color(0xFF22C55E)
                            )
                        }
                    }
                    StageStatus.ACTIVE -> {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = getStageIcon(stageInfo.stage),
                                contentDescription = "Active",
                                modifier = Modifier.size(14.dp),
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                    StageStatus.SKIPPED -> {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Filled.SkipNext,
                                contentDescription = "Skipped",
                                modifier = Modifier.size(14.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    StageStatus.FAILED -> {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.error.copy(alpha = 0.2f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Outlined.Close,
                                contentDescription = "Failed",
                                modifier = Modifier.size(14.dp),
                                tint = MaterialTheme.colorScheme.error
                            )
                        }
                    }
                    StageStatus.PENDING -> {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.surfaceVariant),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Outlined.Pending,
                                contentDescription = "Pending",
                                modifier = Modifier.size(14.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            // Connecting line
            if (!isLast) {
                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .height(32.dp)
                        .background(
                            when (stageInfo.status) {
                                StageStatus.COMPLETED -> Color(0xFF22C55E)
                                StageStatus.ACTIVE -> MaterialTheme.colorScheme.primaryContainer
                                else -> MaterialTheme.colorScheme.outlineVariant
                            }
                        )
                )
            }
        }

        // Content column
        Column(
            modifier = Modifier
                .padding(start = 12.dp)
                .then(if (!isLast) Modifier.padding(bottom = 16.dp) else Modifier)
        ) {
            Text(
                text = stageInfo.label,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = if (stageInfo.status == StageStatus.ACTIVE) FontWeight.SemiBold else FontWeight.Normal,
                color = when (stageInfo.status) {
                    StageStatus.ACTIVE -> MaterialTheme.colorScheme.primary
                    StageStatus.COMPLETED -> MaterialTheme.colorScheme.onSurface
                    StageStatus.SKIPPED, StageStatus.PENDING -> MaterialTheme.colorScheme.onSurfaceVariant
                    StageStatus.FAILED -> MaterialTheme.colorScheme.error
                }
            )
            if (stageInfo.detail != null) {
                Text(
                    text = stageInfo.detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
            if (stageInfo.duration != null) {
                Text(
                    text = formatDuration(stageInfo.duration),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
        }
    }
}

private fun getStageIcon(stage: PipelineStage): ImageVector = when (stage) {
    PipelineStage.BOOTSTRAP -> Icons.Outlined.Download
    PipelineStage.INDEX -> Icons.Outlined.Analytics
    PipelineStage.CLARIFY -> Icons.Outlined.HelpOutline
    PipelineStage.INTENT -> Icons.Outlined.Psychology
    PipelineStage.PLAN -> Icons.Outlined.Map
    PipelineStage.CODE -> Icons.Outlined.Code
    PipelineStage.REVIEW -> Icons.Outlined.Preview
    PipelineStage.TEST -> Icons.Outlined.Science
    PipelineStage.KNOWLEDGE -> Icons.Outlined.School
}

private fun formatDuration(duration: Duration): String {
    val seconds = duration.inWholeSeconds
    return when {
        seconds < 60 -> "${seconds}s"
        seconds < 3600 -> "${seconds / 60}m ${seconds % 60}s"
        else -> "${seconds / 3600}h ${(seconds % 3600) / 60}m"
    }
}
