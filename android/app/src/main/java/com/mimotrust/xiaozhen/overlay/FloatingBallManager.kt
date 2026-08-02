package com.mimotrust.xiaozhen.overlay

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.ContextCompat

object FloatingBallManager {
    private const val PREFS_NAME = "floating_ball_preferences"
    private const val KEY_ENABLED = "enabled"

    fun isEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).getBoolean(KEY_ENABLED, false)

    fun canDraw(context: Context): Boolean = Settings.canDrawOverlays(context)

    fun permissionIntent(context: Context): Intent = Intent(
        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
        Uri.parse("package:${context.packageName}"),
    )

    fun enable(context: Context) {
        if (!canDraw(context)) return
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit().putBoolean(KEY_ENABLED, true).apply()
        ContextCompat.startForegroundService(context, Intent(context, FloatingBallService::class.java))
    }

    fun disable(context: Context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit().putBoolean(KEY_ENABLED, false).apply()
        context.stopService(Intent(context, FloatingBallService::class.java))
    }

    fun restore(context: Context) {
        if (isEnabled(context) && canDraw(context)) enable(context)
    }

    fun attention(context: Context) {
        if (!isEnabled(context) || !canDraw(context)) return
        ContextCompat.startForegroundService(
            context,
            Intent(context, FloatingBallService::class.java).setAction(FloatingBallService.ACTION_ATTENTION),
        )
    }

    fun failed(context: Context) {
        if (!isEnabled(context) || !canDraw(context)) return
        ContextCompat.startForegroundService(
            context,
            Intent(context, FloatingBallService::class.java).setAction(FloatingBallService.ACTION_FAILED),
        )
    }

    fun resolving(context: Context) {
        if (!isEnabled(context) || !canDraw(context)) return
        ContextCompat.startForegroundService(
            context,
            Intent(context, FloatingBallService::class.java).setAction(FloatingBallService.ACTION_RESOLVING),
        )
    }
}
