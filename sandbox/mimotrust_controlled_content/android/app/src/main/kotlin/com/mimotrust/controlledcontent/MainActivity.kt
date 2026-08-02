package com.mimotrust.controlledcontent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject

class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null
    private var requestReceiverRegistered = false
    private val requestReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action != REQUEST_ACTION) return
            val requestId = intent.getStringExtra(REQUEST_ID_EXTRA).orEmpty()
            if (!UUID_PATTERN.matches(requestId)) {
                Log.w(LOG_TAG, "CONTENT_CONTEXT_REQUEST_REJECTED reason=invalid_request_id")
                return
            }
            channel?.invokeMethod(METHOD_REQUEST_CURRENT_CONTEXT, requestId)
            Log.i(LOG_TAG, "CONTENT_CONTEXT_REQUEST_RECEIVED request_id=$requestId")
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL_NAME)
        channel!!
            .setMethodCallHandler { call, result ->
                if (call.method != METHOD_SEND_CONTENT_CONTEXT) {
                    result.notImplemented()
                    return@setMethodCallHandler
                }

                val payload = call.arguments as? String
                if (payload.isNullOrBlank()) {
                    result.error("INVALID_PAYLOAD", "payload must be a non-empty string", null)
                    return@setMethodCallHandler
                }
                if (payload.toByteArray(Charsets.UTF_8).size > MAX_PAYLOAD_BYTES) {
                    result.error("PAYLOAD_TOO_LARGE", "payload exceeds 32 KB", null)
                    return@setMethodCallHandler
                }

                val metadata = try {
                    val json = JSONObject(payload)
                    val contentRef = json.getJSONObject("content_ref")
                    Triple(
                        json.getString("event_id"),
                        contentRef.getString("content_type"),
                        json.getString("trigger"),
                    )
                } catch (_: Exception) {
                    result.error("INVALID_PAYLOAD", "payload is not a valid content context", null)
                    return@setMethodCallHandler
                }

                try {
                    sendBroadcast(
                        Intent(BROADCAST_ACTION)
                            .setPackage(GUARDIAN_PACKAGE)
                            .putExtra(PAYLOAD_EXTRA, payload),
                    )
                    Log.i(
                        LOG_TAG,
                        "CONTENT_CONTEXT_SEND event_id=${metadata.first} " +
                            "type=${metadata.second} trigger=${metadata.third}",
                    )
                    result.success(null)
                } catch (error: RuntimeException) {
                    Log.w(LOG_TAG, "CONTENT_CONTEXT_SEND_FAILED error=${error.javaClass.simpleName}")
                    result.error("BROADCAST_FAILED", "content context broadcast failed", null)
                }
            }
    }

    override fun onResume() {
        super.onResume()
        if (requestReceiverRegistered) return
        val filter = IntentFilter(REQUEST_ACTION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(requestReceiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(requestReceiver, filter)
        }
        requestReceiverRegistered = true
    }

    override fun onPause() {
        if (requestReceiverRegistered) {
            unregisterReceiver(requestReceiver)
            requestReceiverRegistered = false
        }
        super.onPause()
    }

    private companion object {
        const val CHANNEL_NAME = "com.mimotrust.controlledcontent/context"
        const val METHOD_SEND_CONTENT_CONTEXT = "sendContentContext"
        const val METHOD_REQUEST_CURRENT_CONTEXT = "requestCurrentContentContext"
        const val BROADCAST_ACTION = "com.mimotrust.intent.action.CONTENT_CONTEXT"
        const val REQUEST_ACTION = "com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT"
        const val REQUEST_ID_EXTRA = "request_id"
        const val GUARDIAN_PACKAGE = "com.mimotrust.guardian"
        const val PAYLOAD_EXTRA = "payload"
        const val LOG_TAG = "MiMoTrustSandbox"
        const val MAX_PAYLOAD_BYTES = 32 * 1024
        val UUID_PATTERN = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    }
}
