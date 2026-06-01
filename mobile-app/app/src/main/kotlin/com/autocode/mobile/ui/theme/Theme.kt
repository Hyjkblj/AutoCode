package com.autocode.mobile.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val AmberLightColorScheme = lightColorScheme(
    primary = AmberPrimary,
    onPrimary = AmberOnPrimary,
    primaryContainer = AmberPrimaryContainer,
    onPrimaryContainer = AmberOnPrimaryContainer,
    secondary = AmberSecondary,
    onSecondary = AmberOnSecondary,
    secondaryContainer = AmberSecondaryContainer,
    onSecondaryContainer = AmberOnSecondaryContainer,
    tertiary = AmberTertiary,
    onTertiary = AmberOnTertiary,
    tertiaryContainer = AmberTertiaryContainer,
    onTertiaryContainer = AmberOnTertiaryContainer,
    error = AmberError,
    onError = AmberOnError,
    errorContainer = AmberErrorContainer,
    onErrorContainer = AmberOnErrorContainer,
    background = AmberBackground,
    onBackground = AmberOnBackground,
    surface = AmberSurface,
    onSurface = AmberOnSurface,
    surfaceVariant = AmberSurfaceVariant,
    onSurfaceVariant = AmberOnSurfaceVariant,
    outline = AmberOutline,
    outlineVariant = AmberOutlineVariant,
    inverseSurface = AmberInverseSurface,
    inverseOnSurface = AmberInverseOnSurface,
    inversePrimary = AmberInversePrimary,
    surfaceContainerLow = AmberSurfaceContainerLow,
    surfaceContainer = AmberSurfaceContainer,
    surfaceContainerHigh = AmberSurfaceContainerHigh,
    surfaceBright = AmberSurfaceBright,
)

private val AmberDarkColorScheme = darkColorScheme(
    primary = AmberDarkPrimary,
    onPrimary = AmberDarkOnPrimary,
    primaryContainer = AmberDarkPrimaryContainer,
    onPrimaryContainer = AmberDarkOnPrimaryContainer,
    secondary = AmberDarkSecondary,
    onSecondary = AmberDarkOnSecondary,
    secondaryContainer = AmberDarkSecondaryContainer,
    onSecondaryContainer = AmberDarkOnSecondaryContainer,
    tertiary = AmberDarkTertiary,
    onTertiary = AmberDarkOnTertiary,
    tertiaryContainer = AmberDarkTertiaryContainer,
    onTertiaryContainer = AmberDarkOnTertiaryContainer,
    error = AmberDarkError,
    onError = AmberDarkOnError,
    errorContainer = AmberDarkErrorContainer,
    onErrorContainer = AmberDarkOnErrorContainer,
    background = AmberDarkBackground,
    onBackground = AmberDarkOnBackground,
    surface = AmberDarkSurface,
    onSurface = AmberDarkOnSurface,
    surfaceVariant = AmberDarkSurfaceVariant,
    onSurfaceVariant = AmberDarkOnSurfaceVariant,
    outline = AmberDarkOutline,
    outlineVariant = AmberDarkOutlineVariant,
    inverseSurface = AmberDarkInverseSurface,
    inverseOnSurface = AmberDarkInverseOnSurface,
    inversePrimary = AmberDarkInversePrimary,
    surfaceContainerLow = AmberDarkSurfaceContainerLow,
    surfaceContainer = AmberDarkSurfaceContainer,
    surfaceContainerHigh = AmberDarkSurfaceContainerHigh,
    surfaceBright = AmberDarkSurfaceBright,
)

@Composable
fun AutoCodeMobileTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> AmberDarkColorScheme
        else -> AmberLightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = AmberTypography,
        content = content
    )
}
