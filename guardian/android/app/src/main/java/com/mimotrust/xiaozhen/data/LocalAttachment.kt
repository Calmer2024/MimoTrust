package com.mimotrust.xiaozhen.data

import android.net.Uri

data class LocalAttachment(
    val uri: Uri? = null,
    val bytes: ByteArray? = null,
    val filename: String? = null,
    val mimeType: String? = null,
) {
    init {
        require((uri == null) != (bytes == null)) {
            "Exactly one attachment source is required"
        }
    }
}

data class StoredAttachment(
    val uri: String,
    val filename: String,
    val mimeType: String,
)
