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
    @SerializedName("verification_mode") val verificationMode: String = "speed",
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

data class ClaimCheckDto(
    @SerializedName("claim_id") val claimId: String? = null,
    val claim: String? = null,
    val verdict: String? = null,
    val basis: String? = null,
    val uncertainty: String? = null,
)

data class NarrativeAnalysisDto(
    val verdict: String? = null,
    val methods: List<String>? = null,
    val explanation: String? = null,
)

data class EvidenceDto(
    val title: String? = null,
    val url: String? = null,
)

data class VerificationDetailsDto(
    @SerializedName("claim_checks") val claimChecks: List<ClaimCheckDto>? = null,
    @SerializedName("narrative_analysis") val narrativeAnalysis: NarrativeAnalysisDto? = null,
    @SerializedName("evidence_gaps") val evidenceGaps: List<String>? = null,
    @SerializedName("evidence_used") val evidenceUsed: List<EvidenceDto>? = null,
)

data class AnalysisDto(val verification: VerificationDetailsDto? = null)

data class JobResultDto(
    val card: MobileCardDto,
    val analysis: AnalysisDto? = null,
)

