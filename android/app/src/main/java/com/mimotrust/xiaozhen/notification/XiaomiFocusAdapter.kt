package com.mimotrust.xiaozhen.notification

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.Icon
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.mimotrust.xiaozhen.MainActivity
import com.mimotrust.xiaozhen.R
import com.mimotrust.xiaozhen.data.local.JobEntity
import org.json.JSONObject

/**
 * Xiaomi HyperOS 3 Super Island adapter.
 * The payload is only published when the system confirms focus-notification permission for this
 * exact package. Xiaomi still requires the package, channel and business scene to be approved.
 */
class XiaomiFocusAdapter(private val context: Context) {
    fun protocolVersion(): Int = runCatching {
        Settings.System.getInt(context.contentResolver, "notification_focus_protocol", 0)
    }.getOrDefault(0)

    fun hasFocusPermission(): Boolean = runCatching {
        val extras = Bundle().apply { putString("package", context.packageName) }
        context.contentResolver.call(
            Uri.parse("content://miui.statusbar.notification.public"),
            "canShowFocus",
            null,
            extras,
        )?.getBoolean("canShowFocus", false) == true
    }.getOrDefault(false)

    fun isEligible(): Boolean =
        Build.MANUFACTURER.equals("Xiaomi", ignoreCase = true) &&
            protocolVersion() >= 3 &&
            hasFocusPermission()

    fun publishApprovedTemplate(job: JobEntity): Boolean {
        if (!isEligible()) return false
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) return false
        val pendingIntent = PendingIntent.getActivity(
            context,
            job.jobId.hashCode(),
            Intent(context, MainActivity::class.java).putExtra("job_id", job.jobId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, VerificationNotifier.CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_shield)
            .setContentTitle(islandTitle(job))
            .setContentText(islandContent(job))
            .setStyle(NotificationCompat.BigTextStyle().bigText(islandContent(job)))
            .setContentIntent(pendingIntent)
            .setOnlyAlertOnce(true)
            .setOngoing(job.status == "queued" || job.status == "running")
            .setAutoCancel(job.status == "completed")
            .build()

        val pictures = Bundle().apply {
            putParcelable(PICTURE_KEY, Icon.createWithResource(context, R.drawable.xiaozhen_logo))
        }
        notification.extras.putBundle("miui.focus.pics", pictures)
        notification.extras.putString("miui.focus.param", islandPayload(job).toString())
        NotificationManagerCompat.from(context).notify(job.jobId.hashCode(), notification)
        return true
    }

    private fun islandPayload(job: JobEntity): JSONObject {
        val completed = job.status == "completed"
        val textInfo = JSONObject()
            .put("frontTitle", if (completed) "核验完成" else "小真核验")
            .put("title", islandTitle(job))
            .put("content", islandContent(job))
            .put("useHighLight", completed)
        val pictureInfo = JSONObject().put("type", 1).put("pic", PICTURE_KEY)
        val imageTextInfo = JSONObject()
            .put("type", 1)
            .put("picInfo", pictureInfo)
            .put("miui.focus.paramtextInfo", textInfo)
        val island = JSONObject()
            .put("islandProperty", 1)
            .put("islandTimeout", if (completed) 300 else 900)
            .put("bigIslandArea", JSONObject().put("imageTextInfoLeft", imageTextInfo))
            .put("smallIslandArea", JSONObject().put("picInfo", pictureInfo))
        val param = JSONObject()
            .put("protocol", 1)
            .put("business", APPROVED_BUSINESS_SCENE)
            .put("enableFloat", completed)
            .put("updatable", true)
            .put("ticker", islandTitle(job))
            .put("tickerPic", PICTURE_KEY)
            .put("aodTitle", islandTitle(job))
            .put("aodPic", PICTURE_KEY)
            .put("orderId", job.jobId)
            .put("sequence", job.sequence)
            .put("param_island", island)
            .put(
                "baseInfo",
                JSONObject().put("title", islandTitle(job)).put("content", islandContent(job)).put("type", 2),
            )
        return JSONObject().put("param_v2", param)
    }

    private fun islandTitle(job: JobEntity): String = when {
        job.status == "completed" -> job.verdict ?: "核验完成"
        job.status == "failed" || job.status == "cancelled" -> "本次未完成"
        job.progress < 20 -> "正在读取视频"
        job.progress < 45 -> "正在识别关键主张"
        job.progress < 80 -> "正在查找并比对来源"
        else -> "即将完成"
    }

    private fun islandContent(job: JobEntity): String = when {
        job.status == "completed" -> job.conclusion ?: job.displayText
        else -> "${job.displayText} · ${job.progress}%"
    }

    companion object {
        // Must match the final scene code approved by Xiaomi before production signing.
        private const val APPROVED_BUSINESS_SCENE = "content_verification"
        private const val PICTURE_KEY = "miui.focus.pic_xiaozhen"
    }
}
