package com.mimotrust.xiaozhen.notification

import android.content.Context
import android.os.Build
import android.provider.Settings
import com.mimotrust.xiaozhen.data.local.JobEntity

/**
 * Vendor seam for Xiaomi Focus Notification / HyperIsland.
 * Publishing intentionally remains disabled until Xiaomi approves the fixed package,
 * channel and notification-node JSON. The normal Android notification is always valid.
 */
class XiaomiFocusAdapter(private val context: Context) {
    fun protocolVersion(): Int = runCatching {
        Settings.System.getInt(context.contentResolver, "notification_focus_protocol", 0)
    }.getOrDefault(0)

    fun isEligible(): Boolean = Build.MANUFACTURER.equals("Xiaomi", ignoreCase = true) && protocolVersion() >= 2

    fun publishApprovedTemplate(job: JobEntity): Boolean {
        // Adapter boundary reserved for Xiaomi-approved `miui.focus.param` payloads.
        // Returning false guarantees a standard notification fallback before approval.
        return false
    }
}

