package com.mimotrust.xiaozhen.integration

/** Reserved contract for Xiaomi Agent ecosystem current-scene context or a future owned video platform API. */
interface XiaozhenAgentGateway {
    suspend fun verifyCurrentContent(contextReference: String, clientRequestId: String): String
}

