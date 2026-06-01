package com.autocode.mobile.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Timeline
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

enum class EventStatus { SUCCESS, ACTIVE, PENDING, FAILED }

data class TimelineEventData(
    val timestamp: Instant,
    val type: String,
    val description: String,
    val status: EventStatus,
)

@Composable
fun EventTimeline(
    events: List<TimelineEventData>,
    modifier: Modifier = Modifier,
    maxVisible: Int = 6
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.Timeline,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.primary
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "事件流",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Events
            val visibleEvents = events.takeLast(maxVisible)
            visibleEvents.forEach { event ->
                TimelineRow(event = event)
                if (event != visibleEvents.last()) {
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun TimelineRow(event: TimelineEventData) {
    val timeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss")
        .withZone(ZoneId.systemDefault())

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top
    ) {
        // Status dot
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(getEventStatusColor(event.status))
        )

        Spacer(modifier = Modifier.width(12.dp))

        // Timestamp
        Text(
            text = timeFormatter.format(event.timestamp),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(56.dp)
        )

        Spacer(modifier = Modifier.width(8.dp))

        // Description
        Text(
            text = event.description,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun getEventStatusColor(status: EventStatus): Color = when (status) {
    EventStatus.SUCCESS -> Color(0xFF22C55E)
    EventStatus.ACTIVE -> MaterialTheme.colorScheme.primary
    EventStatus.PENDING -> MaterialTheme.colorScheme.outlineVariant
    EventStatus.FAILED -> MaterialTheme.colorScheme.error
}
