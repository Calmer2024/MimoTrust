package com.mimotrust.xiaozhen.data

import com.google.gson.Gson
import com.mimotrust.xiaozhen.BuildConfig
import com.mimotrust.xiaozhen.data.local.JobDao
import com.mimotrust.xiaozhen.data.local.JobEntity
import com.mimotrust.xiaozhen.data.remote.CreateJobRequestDto
import com.mimotrust.xiaozhen.data.remote.ContentMetadataDto
import com.mimotrust.xiaozhen.data.remote.JobEventDto
import com.mimotrust.xiaozhen.data.remote.JobSourceDto
import com.mimotrust.xiaozhen.data.remote.MimoApi
import com.mimotrust.xiaozhen.notification.VerificationNotifier
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources

class JobRepository(
    private val api: MimoApi,
    private val okHttpClient: OkHttpClient,
    private val dao: JobDao,
    private val notifier: VerificationNotifier,
    private val deviceId: String,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val gson = Gson()
    private val streams = mutableMapOf<String, EventSource>()
    private val eventGate = MonotonicEventGate()

    fun observeJobs(): Flow<List<JobEntity>> = dao.observeAll()
    fun observeJob(jobId: String): Flow<JobEntity?> = dao.observe(jobId)

    suspend fun createSharedJob(
        text: String,
        clientRequestId: String,
        verificationMode: String = "speed",
    ): String {
        val response = api.createJob(
            deviceId,
            CreateJobRequestDto(
                source = JobSourceDto(
                    type = if (containsHttpUrl(text)) "shared_url" else "agent_context",
                    value = text,
                    platformHint = platformHint(text),
                ),
                verificationMode = verificationMode,
                clientRequestId = clientRequestId,
            ),
        )
        dao.upsert(
            JobEntity(
                jobId = response.jobId,
                sourceText = text.take(500),
                status = response.status,
                stage = "queued",
                displayText = "小真已接收，等待开始核验",
                progress = 0,
                sequence = 0,
                elapsedMs = 0,
                createdAt = response.createdAt,
            )
        )
        notifier.showQueued(response.jobId)
        observeEvents(response.jobId)
        return response.jobId
    }

    suspend fun reconnectActiveJobs() {
        dao.active().forEach { observeEvents(it.jobId) }
    }

    @Synchronized
    fun observeEvents(jobId: String) {
        if (streams.containsKey(jobId)) return
        scope.launch {
            val current = dao.get(jobId)
            val request = Request.Builder()
                .url(BuildConfig.MIMO_API_BASE_URL + "v1/jobs/$jobId/events")
                .header("Last-Event-ID", (current?.sequence ?: 0).toString())
                .build()
            val source = EventSources.createFactory(okHttpClient)
                .newEventSource(request, listener(jobId))
            synchronized(this@JobRepository) { streams[jobId] = source }
        }
    }

    private fun listener(jobId: String) = object : EventSourceListener() {
        override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
            val event = runCatching { gson.fromJson(data, JobEventDto::class.java) }.getOrNull() ?: return
            scope.launch {
                eventGate.apply(
                    jobId = jobId,
                    incomingSequence = event.sequence,
                    currentSequence = { dao.get(jobId)?.sequence ?: Int.MAX_VALUE },
                    update = {
                        val old = dao.get(jobId) ?: return@apply
                        val status = when (event.state) {
                            "completed" -> "completed"
                            "failed" -> "failed"
                            "cancelled" -> "cancelled"
                            else -> "running"
                        }
                        val updated = old.copy(
                            status = status,
                            stage = event.stage,
                            displayText = event.displayText,
                            progress = event.progressHint,
                            sequence = event.sequence,
                            elapsedMs = event.elapsedMs,
                            extractedMetadata = event.contentMetadata
                                ?.let(::formatContentMetadata)
                                ?: old.extractedMetadata,
                        )
                        dao.upsert(updated)
                        notifier.showProgress(updated)
                        if (status == "completed") loadResult(jobId)
                    },
                )
            }
        }

        override fun onClosed(eventSource: EventSource) {
            synchronized(this@JobRepository) { streams.remove(jobId) }
        }

        override fun onFailure(eventSource: EventSource, t: Throwable?, response: okhttp3.Response?) {
            synchronized(this@JobRepository) { streams.remove(jobId) }
            scope.launch {
                delay(2_000)
                if (dao.get(jobId)?.status in setOf("queued", "running")) observeEvents(jobId)
            }
        }
    }

    private suspend fun loadResult(jobId: String) {
        val response = api.result(jobId)
        val result = response.card
        val analysis = response.analysis
        val details = analysis?.verification
        val old = dao.get(jobId) ?: return
        val completed = old.copy(
            status = "completed",
            verdict = result.verdict,
            headline = result.headline,
            conclusion = result.conclusion,
            evidenceCount = result.evidenceCount,
            elapsedMs = result.elapsedMs,
            sharingAdvice = details?.sharingAdvice?.trim()?.takeIf { it.isNotEmpty() },
            uncertaintyNote = result.uncertaintyNote?.trim()?.takeIf { it.isNotEmpty() },
            reportUrl = result.reportUrl,
            aiDisclaimer = result.aiDisclaimer,
            extractedMetadata = analysis?.metadata?.let { metadata ->
                formatContentMetadata(
                    metadata = metadata,
                    strategy = analysis.strategy,
                    topic = analysis.structuredData?.topic,
                    claimCount = analysis.structuredData?.claims?.size,
                    transcriptChars = analysis.transcriptChars,
                )
            } ?: old.extractedMetadata,
            claimDetails = details?.claimChecks
                ?.mapNotNull { item ->
                    val claim = item.claim?.trim().orEmpty()
                    if (claim.isEmpty()) return@mapNotNull null
                    buildString {
                        append(listOfNotNull(item.claimId, item.verdict).joinToString(" · "))
                        if (isNotEmpty()) append('\n')
                        append(claim)
                        item.basis?.trim()?.takeIf { it.isNotEmpty() }?.let { append("\n").append(it) }
                        item.uncertainty?.trim()?.takeIf { it.isNotEmpty() }?.let { append("\n不确定性：").append(it) }
                    }
                }
                ?.joinToString("\n\n")
                ?.takeIf { it.isNotBlank() },
            narrativeAnalysis = details?.narrativeAnalysis?.let { narrative ->
                listOfNotNull(
                    narrative.verdict?.trim(),
                    narrative.methods?.filter { it.isNotBlank() }?.joinToString("、"),
                    narrative.explanation?.trim(),
                ).filter { it.isNotBlank() }.joinToString("\n").takeIf { it.isNotBlank() }
            },
            evidenceGaps = details?.evidenceGaps
                ?.filter { it.isNotBlank() }
                ?.joinToString("\n")
                ?.takeIf { it.isNotBlank() },
            keyEvidence = details?.evidenceUsed
                ?.mapNotNull { evidence ->
                    evidence.title?.trim()?.takeIf { it.isNotEmpty() }?.let { title ->
                        val prefix = listOfNotNull(
                            evidence.id?.trim()?.takeIf { it.isNotEmpty() },
                            evidence.sourceName?.trim()?.takeIf { it.isNotEmpty() },
                        ).joinToString(" · ")
                        val label = if (prefix.isEmpty()) title else "$prefix · $title"
                        evidence.url?.trim()?.takeIf { it.isNotEmpty() }
                            ?.let { "$label\n$it" } ?: label
                    }
                }
                ?.joinToString("\n\n")
                ?.takeIf { it.isNotBlank() },
        )
        dao.upsert(completed)
        notifier.showResult(completed)
    }

    private fun platformHint(text: String): String? = when {
        "douyin.com" in text || "抖音" in text -> "douyin"
        "kuaishou.com" in text || "快手" in text -> "kuaishou"
        "xiaohongshu.com" in text || "小红书" in text -> "xiaohongshu"
        "bilibili.com" in text || "b23.tv" in text -> "bilibili"
        else -> null
    }

    private fun containsHttpUrl(text: String): Boolean =
        Regex("https?://\\S+", RegexOption.IGNORE_CASE).containsMatchIn(text)

    private fun formatContentMetadata(
        metadata: ContentMetadataDto,
        strategy: String? = metadata.strategy,
        topic: String? = metadata.topic,
        claimCount: Int? = metadata.claimCount,
        transcriptChars: Int? = metadata.transcriptChars,
    ): String? {
        val lines = buildList {
            metadata.title?.trim()?.takeIf { it.isNotEmpty() }?.let { add("标题｜$it") }
            metadata.platform?.trim()?.takeIf { it.isNotEmpty() }?.let { add("平台｜$it") }
            metadata.uploader?.trim()?.takeIf { it.isNotEmpty() }?.let { add("发布者｜$it") }
            metadata.durationSeconds?.takeIf { it > 0 }?.let { seconds ->
                val totalSeconds = seconds.toInt()
                add("时长｜%d:%02d".format(totalSeconds / 60, totalSeconds % 60))
            }
            topic?.trim()?.takeIf { it.isNotEmpty() }?.let { add("主题｜$it") }
            claimCount?.let { add("主张｜已提取 $it 条") }
            transcriptChars?.takeIf { it > 0 }?.let { add("文本｜${it} 字") }
            strategy?.trim()?.takeIf { it.isNotEmpty() }?.let { value ->
                val label = when (value) {
                    "subtitle" -> "字幕"
                    "asr" -> "语音识别"
                    "visual" -> "画面理解"
                    "hybrid" -> "多模态"
                    "metadata" -> "元信息"
                    else -> value
                }
                add("提取方式｜$label")
            }
        }
        return lines.takeIf { it.isNotEmpty() }?.joinToString("\n")
    }
}
