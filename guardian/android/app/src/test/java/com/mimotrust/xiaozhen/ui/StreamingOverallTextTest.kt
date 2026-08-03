package com.mimotrust.xiaozhen.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StreamingOverallTextTest {
    @Test
    fun extractsCompletedCompactOverallReport() {
        val raw = """{"o":["大体可信","补充语境后传播","主要信息有依据，但部分措辞过强",["E1"]]}"""

        assertEquals(
            "综合判定 · 大体可信\n传播建议 · 补充语境后传播\n\n主要信息有依据，但部分措辞过强",
            streamingOverallText(raw),
        )
    }

    @Test
    fun exposesAnIncompleteSummaryWhileItIsStreaming() {
        val raw = """```json
            {"o":["证据不足","谨慎传播","目前没有足够的独立来""".trimIndent()

        assertEquals(
            "综合判定 · 证据不足\n传播建议 · 谨慎传播\n\n目前没有足够的独立来",
            streamingOverallText(raw),
        )
    }

    @Test
    fun ignoresNonReportDeltas() {
        assertNull(streamingOverallText("正在分析来源"))
    }
}
