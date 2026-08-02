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
    private val xiaomi = XiaomiFocusAdapter(context)

    fun createChannel() {
        val channel = NotificationChannel(CHANNEL_ID, "小真核验进度", NotificationManager.IMPORTANCE_DEFAULT).apply {
            description = "显示用户主动发起的内容核验进度与结果"
            setSound(null, null)
        }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    fun showQueued(jobId: String) = notify(
        jobId,
        title = "小真已接收",
        text = "后台核验即将开始",
        progress = 0,
        ongoing = true,
    )

    fun showProgress(job: JobEntity) {
        if (xiaomi.publishApprovedTemplate(job)) return
        notify(job.jobId, "小真正在核验", job.displayText, job.progress, job.status == "running")
    }

    fun showResult(job: JobEntity) {
        if (xiaomi.publishApprovedTemplate(job)) return
        notify(
            job.jobId,
            title = job.headline ?: "核验完成",
            text = job.conclusion ?: job.displayText,
            progress = null,
            ongoing = false,
        )
    }

    private fun notify(jobId: String, title: String, text: String, progress: Int?, ongoing: Boolean) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val intent = Intent(context, MainActivity::class.java).putExtra("job_id", jobId)
        val pendingIntent = PendingIntent.getActivity(
            context,
            jobId.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_shield)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pendingIntent)
            .setOnlyAlertOnce(true)
            .setOngoing(ongoing)
            .setAutoCancel(!ongoing)
        if (progress != null) builder.setProgress(100, progress, progress == 0)
        manager.notify(jobId.hashCode(), builder.build())
    }

    companion object { const val CHANNEL_ID = "mimo_verification_progress" }
}
