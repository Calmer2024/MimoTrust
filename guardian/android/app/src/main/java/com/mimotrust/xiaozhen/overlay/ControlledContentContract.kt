package com.mimotrust.xiaozhen.overlay

import android.content.Context
import android.content.Intent
import org.json.JSONArray
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
    val SUPPORTED_CONTENT_TYPES = setOf(
        "video",
        "audio",
        "article",
        "rich_article",
        "image_gallery",
    )

    private val contentIdPattern = Regex("^[a-z0-9][a-z0-9-]{0,63}$")
    private val contentVersionPattern = Regex("^v[1-9][0-9]*$")
    private val sha256Pattern = Regex("^[0-9a-f]{64}$")

    private data class ParsedCommon(
        val root: JSONObject,
        val eventId: String,
        val contentType: String,
        val content: JSONObject,
    )

    private fun parseCommon(payload: String): ParsedCommon? {
        if (payload.isBlank() || payload.toByteArray(Charsets.UTF_8).size > MAX_PAYLOAD_BYTES) return null
        return runCatching {
            val root = JSONObject(payload)
            if (!root.hasOnlyKeys(
                    "schema_version",
                    "event_id",
                    "trigger",
                    "source_app",
                    "provider",
                    "content_ref",
                    "content_access",
                    "view_state",
                    "observed_at",
                )
            ) return null
            if (root.getString("schema_version") != SCHEMA_VERSION ||
                root.getString("source_app") != "mimotrust_controlled_content"
            ) return null
            val provider = root.getJSONObject("provider")
            if (!provider.hasOnlyKeys("provider_id", "application_id") ||
                provider.getString("provider_id") != PROVIDER_ID ||
                provider.getString("application_id") != SANDBOX_PACKAGE
            ) return null
            val eventId = UUID.fromString(root.getString("event_id")).toString()
            Instant.parse(root.getString("observed_at"))
            val content = root.getJSONObject("content_ref")
            if (!content.hasOnlyKeys(
                    "content_type",
                    "content_id",
                    "content_version",
                    "content_hash",
                    "canonical_url",
                )
            ) return null
            val contentType = content.getString("content_type")
            if (contentType !in SUPPORTED_CONTENT_TYPES ||
                !contentIdPattern.matches(content.getString("content_id")) ||
                !contentVersionPattern.matches(content.getString("content_version")) ||
                !sha256Pattern.matches(content.getString("content_hash")) ||
                !content.getString("canonical_url").startsWith("https://") ||
                !validViewState(contentType, root.getJSONObject("view_state"))
            ) return null
            ParsedCommon(root, eventId, contentType, content)
        }.getOrNull()
    }

    fun parse(payload: String): ControlledContentGrant? {
        return runCatching {
            val parsed = parseCommon(payload) ?: return null
            val trigger = parsed.root.getString("trigger")
            val access = parsed.root.getJSONObject("content_access")
            if (trigger != TRIGGER_GUARDIAN_REQUEST || access.getString("mode") != MODE_GRANT) return null
            if (!access.hasOnlyKeys(
                    "mode",
                    "exchange_url",
                    "grant_code",
                    "audience",
                    "expires_at",
                    "scopes",
                ) ||
                access.getString("audience") != AUDIENCE ||
                access.getString("grant_code").isBlank() ||
                access.getString("grant_code").length > 512 ||
                !access.getString("exchange_url").startsWithAny("http://", "https://") ||
                !access.getJSONArray("scopes").containsAll("manifest:read", "asset:read")
            ) return null
            if (!Instant.parse(access.getString("expires_at")).isAfter(Instant.now())) return null
            ControlledContentGrant(
                eventId = parsed.eventId,
                trigger = trigger,
                contentType = parsed.contentType,
                contentId = parsed.content.getString("content_id"),
                contentVersion = parsed.content.getString("content_version"),
                contentHash = parsed.content.getString("content_hash"),
                exchangeUrl = access.getString("exchange_url"),
                grantCode = access.getString("grant_code"),
                audience = access.getString("audience"),
            )
        }.getOrNull()
    }

    fun isDeferredCandidate(payload: String): Boolean = runCatching {
        val parsed = parseCommon(payload) ?: return false
        val access = parsed.root.getJSONObject("content_access")
        parsed.root.getString("trigger") in setOf("comment", "share") &&
            access.length() == 1 &&
            access.getString("mode") == MODE_DEFERRED
    }.getOrDefault(false)

    private fun validViewState(contentType: String, state: JSONObject): Boolean = when (contentType) {
        "video", "audio" -> runCatching {
            state.hasOnlyKeys("position_ms", "duration_ms", "is_playing") &&
                state.getLong("duration_ms") > 0 &&
                state.getLong("position_ms") in 0..state.getLong("duration_ms") &&
                state.get("is_playing") is Boolean
        }.getOrDefault(false)
        "article", "rich_article" -> runCatching {
            state.hasOnlyKeys("scroll_ratio", "block_index") &&
                state.getDouble("scroll_ratio") in 0.0..1.0 &&
                state.getInt("block_index") >= 0
        }.getOrDefault(false)
        "image_gallery" -> runCatching {
            val count = state.getInt("asset_count")
            state.hasOnlyKeys("active_asset_index", "asset_count") &&
                count > 0 && state.getInt("active_asset_index") in 0 until count
        }.getOrDefault(false)
        else -> false
    }

    private fun JSONObject.hasOnlyKeys(vararg allowed: String): Boolean {
        val expected = allowed.toSet()
        val actual = keys().asSequence().toSet()
        return actual == expected
    }

    private fun JSONArray.containsAll(vararg required: String): Boolean {
        val values = (0 until length()).map { getString(it) }
        return values.size == values.toSet().size && required.all(values::contains)
    }

    private fun String.startsWithAny(vararg prefixes: String): Boolean =
        prefixes.any(::startsWith)
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
