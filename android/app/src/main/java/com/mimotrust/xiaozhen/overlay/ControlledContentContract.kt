package com.mimotrust.xiaozhen.overlay

import android.content.Context
import android.content.Intent
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

data class ControlledContentGrant(
    val eventId: String,
    val trigger: String,
    val contentType: String,
    val contentId: String,
    val contentVersion: String,
    val contentHash: String,
    val exchangeUrl: String,
    val grantCode: String,
    val audience: String,
)

object ControlledContentContract {
    const val REQUEST_ACTION = "com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT"
    const val RESPONSE_ACTION = "com.mimotrust.intent.action.CONTENT_CONTEXT"
    const val REQUEST_ID_EXTRA = "request_id"
    const val PAYLOAD_EXTRA = "payload"
    const val SANDBOX_PACKAGE = "com.mimotrust.controlledcontent"
    const val SCHEMA_VERSION = "2.2"
    const val PROVIDER_ID = "mimotrust_sandbox"
    const val AUDIENCE = "mimotrust_guardian_backend"
    const val TRIGGER_GUARDIAN_REQUEST = "guardian_request"
    const val MODE_DEFERRED = "deferred_grant"
    const val MODE_GRANT = "grant_exchange"
    const val MAX_PAYLOAD_BYTES = 32 * 1024
    val SUPPORTED_CONTENT_TYPES = setOf("video", "article", "rich_article", "image_gallery")

    fun parse(payload: String): ControlledContentGrant? {
        if (payload.isBlank() || payload.toByteArray(Charsets.UTF_8).size > MAX_PAYLOAD_BYTES) return null
        return runCatching {
            val root = JSONObject(payload)
            if (root.getString("schema_version") != SCHEMA_VERSION) return null
            if (root.getString("source_app") != "mimotrust_controlled_content") return null
            val provider = root.getJSONObject("provider")
            if (provider.getString("provider_id") != PROVIDER_ID ||
                provider.getString("application_id") != SANDBOX_PACKAGE
            ) return null
            val eventId = UUID.fromString(root.getString("event_id")).toString()
            val trigger = root.getString("trigger")
            val content = root.getJSONObject("content_ref")
            val contentType = content.getString("content_type")
            if (contentType !in SUPPORTED_CONTENT_TYPES) return null
            val access = root.getJSONObject("content_access")
            if (trigger != TRIGGER_GUARDIAN_REQUEST || access.getString("mode") != MODE_GRANT) return null
            if (access.getString("audience") != AUDIENCE) return null
            if (!Instant.parse(access.getString("expires_at")).isAfter(Instant.now())) return null
            ControlledContentGrant(
                eventId = eventId,
                trigger = trigger,
                contentType = contentType,
                contentId = content.getString("content_id"),
                contentVersion = content.getString("content_version"),
                contentHash = content.getString("content_hash"),
                exchangeUrl = access.getString("exchange_url"),
                grantCode = access.getString("grant_code"),
                audience = access.getString("audience"),
            )
        }.getOrNull()
    }

    fun isDeferredCandidate(payload: String): Boolean = runCatching {
        val root = JSONObject(payload)
        root.getString("schema_version") == SCHEMA_VERSION &&
            root.getJSONObject("provider").getString("provider_id") == PROVIDER_ID &&
            root.getString("trigger") in setOf("comment", "share") &&
            root.getJSONObject("content_access").getString("mode") == MODE_DEFERRED
    }.getOrDefault(false)
}

object ControlledContentRequestCoordinator {
    private const val PREFS = "controlled_content_requests"
    private const val KEY_PENDING_ID = "pending_id"
    private const val KEY_PENDING_AT = "pending_at"
    private const val KEY_LAST_EVENT_ID = "last_event_id"
    const val RESPONSE_TIMEOUT_MS = 5_000L

    fun request(context: Context): String {
        val requestId = UUID.randomUUID().toString()
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_PENDING_ID, requestId)
            .putLong(KEY_PENDING_AT, System.currentTimeMillis())
            .apply()
        context.sendBroadcast(
            Intent(ControlledContentContract.REQUEST_ACTION)
                .setPackage(ControlledContentContract.SANDBOX_PACKAGE)
                .putExtra(ControlledContentContract.REQUEST_ID_EXTRA, requestId)
        )
        return requestId
    }

    fun consume(context: Context, eventId: String): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val pendingId = prefs.getString(KEY_PENDING_ID, null)
        val pendingAt = prefs.getLong(KEY_PENDING_AT, 0L)
        val fresh = System.currentTimeMillis() - pendingAt in 0..RESPONSE_TIMEOUT_MS
        if (!fresh || pendingId != eventId || prefs.getString(KEY_LAST_EVENT_ID, null) == eventId) return false
        prefs.edit().remove(KEY_PENDING_ID).remove(KEY_PENDING_AT).putString(KEY_LAST_EVENT_ID, eventId).apply()
        return true
    }

    fun isPending(context: Context, requestId: String): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return prefs.getString(KEY_PENDING_ID, null) == requestId
    }

    fun cancel(context: Context, requestId: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_PENDING_ID, null) != requestId) return
        prefs.edit().remove(KEY_PENDING_ID).remove(KEY_PENDING_AT).apply()
    }
}
