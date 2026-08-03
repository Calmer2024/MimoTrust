package com.mimotrust.xiaozhen.notification

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.mimotrust.xiaozhen.MainActivity
import com.mimotrust.xiaozhen.R
import com.mimotrust.xiaozhen.data.local.JobEntity

class VerificationNotifier(private val context: Context) {
    private val manager = NotificationManagerCompat.from(context)

    fun createChannel() {
        val resultChannel = NotificationChannel(
            CHANNEL_ID,
            "小真核验结果提醒",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "核验完成后弹出结果卡片，点击可查看完整证据"
            enableVibration(true)
            setShowBadge(true)
        }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(resultChannel)
    }

    fun showQueued(@Suppress("UNUSED_PARAMETER") job: JobEntity) = Unit

    fun showProgress(@Suppress("UNUSED_PARAMETER") job: JobEntity) = Unit

    fun showResult(job: JobEntity) {
        val failed = job.status == "failed" || job.status == "cancelled"
        notify(
            notificationId = job.jobId.hashCode(),
            jobId = job.jobId,
            title = if (failed) "核验未完成" else "核验完成 · ${job.verdict ?: "查看结果"}",
            headline = if (failed) job.displayText else job.headline ?: "小真已完成核验",
            text = job.conclusion ?: job.displayText,
        )
    }

    private fun notify(
        notificationId: Int,
        jobId: String,
        title: String,
        headline: String,
        text: String,
    ) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val intent = Intent(context, MainActivity::class.java).apply {
            putExtra("job_id", jobId)
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            jobId.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_shield)
            .setContentTitle(title)
            .setContentText(headline)
            .setSubText("点击查看完整核验结果")
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .setBigContentTitle(title)
                    .setSummaryText(headline)
                    .bigText(text)
            )
            .setContentIntent(pendingIntent)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setAutoCancel(true)
        manager.notify(notificationId, builder.build())
    }

    companion object {
        const val CHANNEL_ID = "mimo_verification_result_popup_v3"
    }
}
