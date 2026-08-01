package com.mimotrust.xiaozhen

import android.content.Context
import java.util.UUID

object DeviceIdentity {
    fun get(context: Context): String {
        val preferences = context.getSharedPreferences("mimo-device", Context.MODE_PRIVATE)
        return preferences.getString("id", null) ?: UUID.randomUUID().toString().also {
            preferences.edit().putString("id", it).apply()
        }
    }
}

