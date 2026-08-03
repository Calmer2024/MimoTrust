package com.mimotrust.xiaozhen.data

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ConcurrentHashMap

internal class MonotonicEventGate {
    private val locks = ConcurrentHashMap<String, Mutex>()

    suspend fun apply(
        jobId: String,
        incomingSequence: Int,
        currentSequence: suspend () -> Int,
        update: suspend () -> Unit,
    ): Boolean = locks.getOrPut(jobId) { Mutex() }.withLock {
        if (incomingSequence <= currentSequence()) return@withLock false
        update()
        true
    }
}
