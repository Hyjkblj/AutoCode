package com.autocode.mobile.ui.components

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.outlined.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class LogEntry(
    val timestamp: String,
    val icon: String,  // "✓", "→", "⏳", "⚡"
    val message: String,
    val color: LogColor,
)

enum class LogColor { SUCCESS, INFO, WARNING, ACTIVE }

@Composable
fun LogConsole(
    entries: List<LogEntry>,
    modifier: Modifier = Modifier,
    initialExpanded: Boolean = false,
    maxCollapsedLines: Int = 4,
) {
    var expanded by remember { mutableStateOf(initialExpanded) }

    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.animateContentSize()) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Outlined.Terminal,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = MaterialTheme.colorScheme.tertiary
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "实时日志",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(modifier = Modifier.weight(1f))
                IconButton(
                    onClick = { expanded = !expanded },
                    modifier = Modifier.size(24.dp)
                ) {
                    Icon(
                        imageVector = if (expanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                        contentDescription = if (expanded) "收起" else "展开",
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            // Log content
            val displayEntries = if (expanded) entries else entries.takeLast(maxCollapsedLines)
            val scrollState = rememberScrollState()

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = if (expanded) 240.dp else 120.dp)
                    .background(
                        MaterialTheme.colorScheme.surface,
                        RoundedCornerShape(bottomStart = 16.dp, bottomEnd = 16.dp)
                    )
                    .padding(12.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .verticalScroll(scrollState)
                ) {
                    displayEntries.forEach { entry ->
                        LogRow(entry)
                    }
                }
            }
        }
    }
}

@Composable
private fun LogRow(entry: LogEntry) {
    val textColor = when (entry.color) {
        LogColor.SUCCESS -> Color(0xFF22C55E)
        LogColor.INFO -> MaterialTheme.colorScheme.onSurfaceVariant
        LogColor.WARNING -> Color(0xFFF59E0B)
        LogColor.ACTIVE -> MaterialTheme.colorScheme.primary
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 1.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "[${entry.timestamp}]",
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
            modifier = Modifier.width(72.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = entry.icon,
            fontSize = 11.sp,
            modifier = Modifier.width(16.dp)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = entry.message,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            color = textColor,
            lineHeight = 14.sp
        )
    }
}
