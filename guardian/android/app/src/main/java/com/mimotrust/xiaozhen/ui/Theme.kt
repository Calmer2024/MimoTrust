package com.mimotrust.xiaozhen.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight

val Ink = Color(0xFF2C1B15)
val Paper = Color(0xFFF7F6F3)
val Muted = Color(0xFF948B86)
val Soft = Color(0xFFF0EEEA)
val SurfaceSoft = Color(0xFFFFFFFF)
val LightMuted = Color(0xFFB5ACA7)
val Divider = Color(0xFFEDE9E5)
val Orange = Color(0xFFFF684B)
val OrangeSoft = Color(0xFFFFEEE8)
val Cocoa = Color(0xFF46352B)
val Blue = Color(0xFF5684EB)
val BlueSoft = Color(0xFFEEF4FF)
val Cyan = Color(0xFF26B7D5)
val Green = Color(0xFF13C878)
val GreenSoft = Color(0xFFEDF9F3)
val Amber = Color(0xFFFFB44B)
val AmberSoft = Color(0xFFFFF7E7)

private val MimoColors = lightColorScheme(
    primary = Ink,
    onPrimary = Color.White,
    background = Paper,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    outline = Divider,
)

private val MimoTypography = Typography().run {
    copy(
        displayLarge = displayLarge.withRegularWeight(),
        displayMedium = displayMedium.withRegularWeight(),
        displaySmall = displaySmall.withRegularWeight(),
        headlineLarge = headlineLarge.withRegularWeight(),
        headlineMedium = headlineMedium.withRegularWeight(),
        headlineSmall = headlineSmall.withRegularWeight(),
        titleLarge = titleLarge.withRegularWeight(),
        titleMedium = titleMedium.withRegularWeight(),
        titleSmall = titleSmall.withRegularWeight(),
        bodyLarge = bodyLarge.withRegularWeight(),
        bodyMedium = bodyMedium.withRegularWeight(),
        bodySmall = bodySmall.withRegularWeight(),
        labelLarge = labelLarge.withRegularWeight(),
        labelMedium = labelMedium.withRegularWeight(),
        labelSmall = labelSmall.withRegularWeight(),
    )
}

private fun TextStyle.withRegularWeight() = copy(
    fontFamily = FontFamily.SansSerif,
    fontWeight = FontWeight.Normal,
)

@Composable
fun MimoTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = MimoColors, typography = MimoTypography, content = content)
}
