package com.mimotrust.xiaozhen.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Ink = Color(0xFF201713)
val Paper = Color(0xFFFFFFFF)
val Muted = Color(0xFF7C746F)
val Soft = Color(0xFFF4F2F0)
val SurfaceSoft = Color(0xFFF7F6F4)
val LightMuted = Color(0xFFB2AAA5)
val Divider = Color(0xFFE8E4E1)
val Orange = Color(0xFFFF5A1F)
val OrangeSoft = Color(0xFFFFEEE7)

private val MimoColors = lightColorScheme(
    primary = Ink,
    onPrimary = Color.White,
    background = Color.White,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    outline = Divider,
)

@Composable
fun MimoTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = MimoColors, content = content)
}
