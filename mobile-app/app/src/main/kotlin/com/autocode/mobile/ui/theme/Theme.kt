package com.autocode.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val AutoCodeColors = lightColorScheme(
    primary = Color(0xFF2F95DC),
    onPrimary = Color.White,
    secondary = Color(0xFF2F95DC),
    tertiary = Color(0xFF1565C0),
)

@Composable
fun AutoCodeMobileTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AutoCodeColors,
        content = content,
    )
}
