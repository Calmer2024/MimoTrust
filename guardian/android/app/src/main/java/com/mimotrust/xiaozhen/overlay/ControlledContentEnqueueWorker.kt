package com.mimotrust.xiaozhen.overlay

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.mimotrust.xiaozhen.MimoTrustApplication
import java.util.concurrent.TimeUnit

class ControlledContentEnqueueWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val eventId = inputData.getString(KEY_EVENT_ID) ?: return Result.failure()
        val payload = ControlledContentPendingStore.load(applicationContext, eventId)
            ?: return Result.failure()
        return runCatching {
            val jobId = (applicationContext as MimoTrustApplication).repository
                .createControlledContentJob(payload, eventId)
            ControlledContentPendingStore.remove(applicationContext, eventId)
            Log.i(LOG_TAG, "VERIFICATION_JOB_CREATED event_id=$eventId job_id=$jobId")
            Result.success()
        }.getOrElse { error ->
            Log.w(
                LOG_TAG,
                "GUARDIAN_CONTEXT_FAILED event_id=$eventId error=${error.javaClass.simpleName} " +
                    "reason=${error.message.orEmpty().take(160)}",
            )
            if (runAttemptCount < MAX_RETRIES) {
                Result.retry()
            } else {
                ControlledContentPendingStore.remove(applicationContext, eventId)
                FloatingBallManager.failed(applicationContext)
                Result.failure()
            }
        }
    }

    companion object {
        private const val KEY_EVENT_ID = "event_id"
        private const val LOG_TAG = "MiMoTrustGuardian"
        private const val MAX_RETRIES = 1

        fun enqueue(context: Context, eventId: String, payload: String): Boolean = runCatching {
            check(ControlledContentPendingStore.save(context, eventId, payload))
            val request = OneTimeWorkRequestBuilder<ControlledContentEnqueueWorker>()
                .setInputData(Data.Builder().putString(KEY_EVENT_ID, eventId).build())
                .setBackoffCriteria(BackoffPolicy.LINEAR, 10, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                "content-context-$eventId",
                ExistingWorkPolicy.KEEP,
                request,
            )
        }.isSuccess
    }
}

private object ControlledContentPendingStore {
    private const val PREFS = "controlled_content_pending_payloads"

    fun save(context: Context, eventId: String, payload: String): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(eventId, payload)
            .commit()

    fun load(context: Context, eventId: String): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(eventId, null)

    fun remove(context: Context, eventId: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(eventId).apply()
    }
}
