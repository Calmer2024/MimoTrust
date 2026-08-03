package com.mimotrust.xiaozhen.overlay

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Integration seam for an owned video app signed with the same certificate.
 * Third-party apps are deliberately not inspected through accessibility or clipboard APIs.
 */
class VideoContextReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != CurrentVideoContextStore.ACTION_UPDATE_VIDEO_CONTEXT) return
        val url = intent.getStringExtra(CurrentVideoContextStore.EXTRA_VIDEO_URL).orEmpty()
        val interaction = intent.getStringExtra(CurrentVideoContextStore.EXTRA_INTERACTION)
            ?: CurrentVideoContextStore.INTERACTION_VIEW
        CurrentVideoContextStore(context).update(url, interaction)
        if (interaction == CurrentVideoContextStore.INTERACTION_COMMENT ||
            interaction == CurrentVideoContextStore.INTERACTION_SHARE
        ) {
            FloatingBallManager.attention(context)
        }
    }
}
