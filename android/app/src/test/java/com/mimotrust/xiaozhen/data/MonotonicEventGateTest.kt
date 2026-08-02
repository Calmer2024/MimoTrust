package com.mimotrust.xiaozhen.data

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

class MonotonicEventGateTest {
    @Test
    fun concurrentEventsCannotRegressTheStoredSequence() = runTest {
        val gate = MonotonicEventGate()
        var storedSequence = 0

        (1..9).map { sequence ->
            async {
                gate.apply(
                    jobId = "job-one",
                    incomingSequence = sequence,
                    currentSequence = { storedSequence },
                    update = {
                        delay((10 - sequence).toLong())
                        storedSequence = sequence
                    },
                )
            }
        }.awaitAll()

        assertEquals(9, storedSequence)
    }
}
