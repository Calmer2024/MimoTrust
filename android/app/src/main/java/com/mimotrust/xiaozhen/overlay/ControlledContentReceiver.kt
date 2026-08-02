package com.mimotrust.xiaozhen.overlay

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.mimotrust.xiaozhen.BuildConfig
import com.mimotrust.xiaozhen.MimoTrustApplication
import com.mimotrust.xiaozhen.data.remote.MimoApiFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
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
        val grant = ControlledContentContract.parse(payload)
        if (grant == null) {
            Log.w(LOG_TAG, "GUARDIAN_CONTEXT_REJECTED reason=unsupported_or_invalid_payload")
            return
        }
        if (!ControlledContentRequestCoordinator.consume(context, grant.eventId)) return
        Log.i(LOG_TAG, "GUARDIAN_CONTEXT_ACCEPTED event_id=${grant.eventId} content_id=${grant.contentId}")
        FloatingBallManager.resolving(context)
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            runCatching {
                val input = exchangeForAnalysisInput(grant)
                val jobId = (context.applicationContext as MimoTrustApplication).repository.createSharedJob(
                    input.value,
                    UUID.randomUUID().toString(),
                    sourceType = input.sourceType,
                    sourcePlatformHint = input.platformHint,
                    sourceDisplayText = input.displayText,
                )
                Log.i(LOG_TAG, "VERIFICATION_JOB_CREATED event_id=${grant.eventId} job_id=$jobId")
            }.onFailure {
                Log.w(
                    LOG_TAG,
                    "GUARDIAN_CONTEXT_FAILED error=${it.javaClass.simpleName} " +
                        "reason=${it.message.orEmpty().take(160)}",
                )
                FloatingBallManager.failed(context)
            }
            pending.finish()
        }
    }

    private fun exchangeForAnalysisInput(grant: ControlledContentGrant): ControlledAnalysisInput {
        val body = JSONObject()
            .put("exchange_url", grant.exchangeUrl)
            .put("grant_code", grant.grantCode)
            .put("audience", grant.audience)
            .put("content_id", grant.contentId)
            .put("content_version", grant.contentVersion)
            .toString()
            .toRequestBody("application/json; charset=utf-8".toMediaType())
        val request = Request.Builder()
            .url(BuildConfig.MIMO_API_BASE_URL + "v1/controlled-content/exchange")
            .post(body)
            .build()
        MimoApiFactory.httpClient.newCall(request).execute().use { response ->
            check(response.isSuccessful) { "Grant exchange failed: ${response.code}" }
            val root = JSONObject(response.body?.string().orEmpty())
            val manifest = root.getJSONObject("manifest")
            val content = manifest.getJSONObject("content")
            check(content.getString("content_id") == grant.contentId)
            check(content.getString("content_version") == grant.contentVersion)
            check(content.getString("content_hash") == grant.contentHash)
            check(content.getString("content_type") == grant.contentType)
            val assets = manifest.getJSONArray("assets")
            if (grant.contentType == "video") {
                for (index in 0 until assets.length()) {
                    val asset = assets.getJSONObject(index)
                    if (asset.optString("role") == "analysis" &&
                        asset.optString("mime_type").startsWith("video/") &&
                        asset.optString("sha256") == grant.contentHash
                    ) {
                        return ControlledAnalysisInput(
                            value = asset.getString("source_url"),
                            sourceType = "shared_url",
                            platformHint = "mimotrust_sandbox",
                            displayText = "核验 Sandbox 视频：${content.optString("title", "未命名内容")}",
                        )
                    }
                }
                error("Manifest has no matching analysis video")
            }

            val compactAssets = JSONArray()
            for (index in 0 until minOf(assets.length(), 12)) {
                val asset = assets.getJSONObject(index)
                val mimeType = asset.optString("mime_type")
                if (!mimeType.startsWith("image/") && !mimeType.startsWith("text/")) continue
                val compactAsset = JSONObject()
                        .put("asset_id", asset.getString("asset_id"))
                        .put("role", asset.getString("role"))
                        .put("mime_type", mimeType)
                        .put("source_url", asset.getString("source_url"))
                        .put("sha256", asset.getString("sha256"))
                        .put("order", asset.optInt("order", index))
                if (compactAssets.toString().length + compactAsset.toString().length > MAX_ASSET_PAYLOAD_CHARS) break
                compactAssets.put(compactAsset)
            }
            val blockText = buildString {
                val blocks = content.optJSONArray("blocks") ?: JSONArray()
                for (index in 0 until blocks.length()) {
                    val text = blocks.getJSONObject(index).optString("text").trim()
                    if (text.isNotEmpty()) appendLine(text)
                    if (length >= MAX_INLINE_TEXT_CHARS) break
                }
            }.take(MAX_INLINE_TEXT_CHARS)
            val payload = JSONObject()
                .put("kind", CONTROLLED_CONTENT_KIND)
                .put("content_type", grant.contentType)
                .put("title", content.optString("title", "未命名内容"))
                .put("author", content.optString("author"))
                .put("published_at", content.optString("published_at"))
                .put("canonical_url", content.optString("canonical_url"))
                .put("body_asset_id", content.optString("body_asset_id"))
                .put("text", blockText)
                .put("assets", compactAssets)
                .toString()
            val typeLabel = when (grant.contentType) {
                "image_gallery" -> "图文帖子"
                "rich_article" -> "图文长文"
                else -> "文章"
            }
            return ControlledAnalysisInput(
                value = payload,
                sourceType = "agent_context",
                platformHint = "mimotrust_sandbox",
                displayText = "核验 Sandbox $typeLabel：${content.optString("title", "未命名内容")}",
            )
        }
    }

    private data class ControlledAnalysisInput(
        val value: String,
        val sourceType: String,
        val platformHint: String,
        val displayText: String,
    )

    private companion object {
        const val LOG_TAG = "MiMoTrustGuardian"
        const val CONTROLLED_CONTENT_KIND = "mimotrust_controlled_content"
        const val MAX_INLINE_TEXT_CHARS = 2_000
        const val MAX_ASSET_PAYLOAD_CHARS = 6_500
    }
}
