package com.mimotrust.xiaozhen.data.remote

import com.google.gson.annotations.SerializedName

data class JobSourceDto(
    val type: String = "shared_url",
    val value: String,
    @SerializedName("platform_hint") val platformHint: String? = null,
)

data class CreateJobRequestDto(
    val source: JobSourceDto,
    val mode: String = "auto",
    @SerializedName("client_request_id") val clientRequestId: String,
)

data class CreateJobResponseDto(
    @SerializedName("job_id") val jobId: String,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("event_url") val eventUrl: String,
    val reused: Boolean,
)

data class JobEventDto(
    @SerializedName("job_id") val jobId: String,
    val sequence: Int,
    val stage: String,
    val state: String,
    @SerializedName("display_text") val displayText: String,
    @SerializedName("elapsed_ms") val elapsedMs: Long,
    @SerializedName("progress_hint") val progressHint: Int,
)

data class MobileCardDto(
    @SerializedName("job_id") val jobId: String,
    val verdict: String,
    val headline: String,
    val conclusion: String,
    @SerializedName("evidence_count") val evidenceCount: Int,
    @SerializedName("elapsed_ms") val elapsedMs: Long,
)

data class JobResultDto(val card: MobileCardDto)

