package com.mimotrust.xiaozhen.share

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import java.util.UUID

class ShareReceiverActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.action == Intent.ACTION_SEND) {
            val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty().trim()
            if (sharedText.isNotEmpty()) {
                val data = Data.Builder()
                    .putString(ShareEnqueueWorker.KEY_TEXT, sharedText)
                    .putString(ShareEnqueueWorker.KEY_REQUEST_ID, UUID.randomUUID().toString())
                    .build()
                val request = OneTimeWorkRequestBuilder<ShareEnqueueWorker>()
                    .setInputData(data)
                    .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                    .build()
                WorkManager.getInstance(this).enqueue(request)
            }
        }
        finish()
        overridePendingTransition(0, 0)
    }
}

