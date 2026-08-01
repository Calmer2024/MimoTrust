package com.mimotrust.xiaozhen.share

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mimotrust.xiaozhen.MimoTrustApplication

class ShareEnqueueWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val text = inputData.getString(KEY_TEXT) ?: return Result.failure()
        val requestId = inputData.getString(KEY_REQUEST_ID) ?: return Result.failure()
        val repository = (applicationContext as MimoTrustApplication).repository
        return runCatching { repository.createSharedJob(text, requestId) }
            .fold(onSuccess = { Result.success() }, onFailure = { Result.retry() })
    }

    companion object {
        const val KEY_TEXT = "shared_text"
        const val KEY_REQUEST_ID = "client_request_id"
    }
}

