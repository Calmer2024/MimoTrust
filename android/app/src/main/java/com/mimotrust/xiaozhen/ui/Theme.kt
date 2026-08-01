package com.mimotrust.xiaozhen.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Ink = Color(0xFF202020)
val Paper = Color(0xFFF7F7F5)
val Muted = Color(0xFF777773)
val Soft = Color(0xFFECECE8)

private val MimoColors = lightColorScheme(
    primary = Ink,
    onPrimary = Color.White,
    background = Paper,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    outline = Color(0xFFD8D8D3),
)

@Composable
fun MimoTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = MimoColors, content = content)
}

