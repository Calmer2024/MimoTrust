package com.mimotrust.xiaozhen.overlay

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

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
        if (!ControlledContentRequestCoordinator.consume(context, grant.eventId)) {
            Log.w(
                LOG_TAG,
                "GUARDIAN_CONTEXT_REJECTED event_id=${grant.eventId} reason=request_id_mismatch_or_duplicate",
            )
            return
        }
        if (!ControlledContentEnqueueWorker.enqueue(context, grant.eventId, payload)) {
            Log.w(LOG_TAG, "GUARDIAN_CONTEXT_REJECTED event_id=${grant.eventId} reason=enqueue_failed")
            FloatingBallManager.failed(context)
            return
        }
        Log.i(
            LOG_TAG,
            "GUARDIAN_CONTEXT_ACCEPTED event_id=${grant.eventId} " +
                "content_id=${grant.contentId} type=${grant.contentType}",
        )
        FloatingBallManager.resolving(context)
    }

    private companion object {
        const val LOG_TAG = "MiMoTrustGuardian"
    }
}
