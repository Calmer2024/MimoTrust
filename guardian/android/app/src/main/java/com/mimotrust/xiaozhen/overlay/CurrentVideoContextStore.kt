package com.mimotrust.xiaozhen.overlay

import android.content.Context

data class CurrentVideoContext(
    val url: String,
    val interaction: String,
    val updatedAt: Long,
)

class CurrentVideoContextStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun update(url: String, interaction: String) {
        if (!url.startsWith("http://") && !url.startsWith("https://")) return
        preferences.edit()
            .putString(KEY_URL, url)
            .putString(KEY_INTERACTION, interaction)
            .putLong(KEY_UPDATED_AT, System.currentTimeMillis())
            .apply()
    }

    fun current(maxAgeMs: Long = CONTEXT_TTL_MS): CurrentVideoContext? {
        val url = preferences.getString(KEY_URL, null) ?: return null
        val updatedAt = preferences.getLong(KEY_UPDATED_AT, 0L)
        if (System.currentTimeMillis() - updatedAt > maxAgeMs) return null
        return CurrentVideoContext(
            url = url,
            interaction = preferences.getString(KEY_INTERACTION, INTERACTION_VIEW).orEmpty(),
            updatedAt = updatedAt,
        )
    }

    companion object {
        const val ACTION_UPDATE_VIDEO_CONTEXT = "com.mimotrust.xiaozhen.action.UPDATE_VIDEO_CONTEXT"
        const val EXTRA_VIDEO_URL = "video_url"
        const val EXTRA_INTERACTION = "interaction"
        const val INTERACTION_VIEW = "view"
        const val INTERACTION_COMMENT = "comment"
        const val INTERACTION_SHARE = "share"

        private const val PREFS_NAME = "current_video_context"
        private const val KEY_URL = "url"
        private const val KEY_INTERACTION = "interaction"
        private const val KEY_UPDATED_AT = "updated_at"
        private const val CONTEXT_TTL_MS = 90_000L
    }
}
