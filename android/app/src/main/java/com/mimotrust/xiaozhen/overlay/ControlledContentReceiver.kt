package com.mimotrust.xiaozhen.overlay

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.mimotrust.xiaozhen.MimoTrustApplication
import com.mimotrust.xiaozhen.data.remote.MimoApiFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.UUID

class ControlledContentReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ControlledContentContract.RESPONSE_ACTION) return
        val payload = intent.getStringExtra(ControlledContentContract.PAYLOAD_EXTRA).orEmpty()
        if (ControlledContentContract.isDeferredCandidate(payload)) {
            Log.i(LOG_TAG, "CONTEXT_CANDIDATE_RECEIVED")
            FloatingBallManager.attention(context)
            return
        }
        val grant = ControlledContentContract.parse(payload) ?: return
        if (!ControlledContentRequestCoordinator.consume(context, grant.eventId)) return
        Log.i(LOG_TAG, "GUARDIAN_CONTEXT_ACCEPTED event_id=${grant.eventId} content_id=${grant.contentId}")
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            runCatching {
                val videoUrl = exchangeForAnalysisUrl(grant)
                val jobId = (context.applicationContext as MimoTrustApplication).repository.createSharedJob(
                    videoUrl,
                    UUID.randomUUID().toString(),
                )
                Log.i(LOG_TAG, "VERIFICATION_JOB_CREATED event_id=${grant.eventId} job_id=$jobId")
            }.onFailure {
                Log.w(LOG_TAG, "GUARDIAN_CONTEXT_FAILED error=${it.javaClass.simpleName}")
                FloatingBallManager.failed(context)
            }
            pending.finish()
        }
    }

    private fun exchangeForAnalysisUrl(grant: ControlledContentGrant): String {
        val body = JSONObject()
            .put("grant_code", grant.grantCode)
            .put("audience", grant.audience)
            .put("content_id", grant.contentId)
            .put("content_version", grant.contentVersion)
            .toString()
            .toRequestBody("application/json; charset=utf-8".toMediaType())
        val request = Request.Builder().url(grant.exchangeUrl).post(body).build()
        MimoApiFactory.httpClient.newCall(request).execute().use { response ->
            check(response.isSuccessful) { "Grant exchange failed: ${response.code}" }
            val root = JSONObject(response.body?.string().orEmpty())
            val manifest = root.getJSONObject("manifest")
            val content = manifest.getJSONObject("content")
            check(content.getString("content_id") == grant.contentId)
            check(content.getString("content_version") == grant.contentVersion)
            check(content.getString("content_hash") == grant.contentHash)
            val assets = manifest.getJSONArray("assets")
            for (index in 0 until assets.length()) {
                val asset = assets.getJSONObject(index)
                if (asset.optString("role") == "analysis" &&
                    asset.optString("mime_type").startsWith("video/") &&
                    asset.optString("sha256") == grant.contentHash
                ) {
                    return asset.getString("source_url")
                }
            }
            error("Manifest has no matching analysis video")
        }
    }

    private companion object {
        const val LOG_TAG = "MiMoTrustGuardian"
    }
}
