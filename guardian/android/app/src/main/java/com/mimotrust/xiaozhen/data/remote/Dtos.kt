package com.mimotrust.xiaozhen.data.remote

import com.google.gson.JsonObject
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

data class ControlledContentSubmissionDto(
    @SerializedName("request_id") val requestId: String,
    @SerializedName("guardian_app_version") val guardianAppVersion: String,
    val context: JsonObject,
)

data class JobEventDto(
    @SerializedName("job_id") val jobId: String,
    val sequence: Int,
    val stage: String,
    val state: String,
    @SerializedName("display_text") val displayText: String,
    @SerializedName("elapsed_ms") val elapsedMs: Long,
    @SerializedName("progress_hint") val progressHint: Int,
    @SerializedName("content_metadata") val contentMetadata: ContentMetadataDto? = null,
    @SerializedName("event_kind") val eventKind: String = "stage",
    val payload: JobEventPayloadDto? = null,
)

data class ContentMetadataDto(
    val title: String? = null,
    val platform: String? = null,
    val uploader: String? = null,
    @SerializedName("duration_seconds") val durationSeconds: Double? = null,
    @SerializedName("content_type") val contentType: String? = null,
    val strategy: String? = null,
    val topic: String? = null,
    @SerializedName("claim_count") val claimCount: Int? = null,
    @SerializedName("transcript_chars") val transcriptChars: Int? = null,
)

data class JobEventPayloadDto(
    val text: String? = null,
    val kind: String? = null,
    val title: String? = null,
    val summary: String? = null,
    val items: List<JobArtifactItemDto>? = null,
)

data class JobArtifactItemDto(
    val label: String? = null,
    val text: String? = null,
    val meta: String? = null,
    val url: String? = null,
)

data class MobileCardDto(
    @SerializedName("job_id") val jobId: String,
    val verdict: String,
    val headline: String,
    val conclusion: String,
    @SerializedName("evidence_count") val evidenceCount: Int,
    @SerializedName("elapsed_ms") val elapsedMs: Long,
    @SerializedName("key_evidence") val keyEvidence: List<EvidenceDto>? = null,
    @SerializedName("uncertainty_note") val uncertaintyNote: String? = null,
    @SerializedName("report_url") val reportUrl: String? = null,
    @SerializedName("ai_disclaimer") val aiDisclaimer: String? = null,
)

data class ClaimCheckDto(
    @SerializedName("claim_id") val claimId: String? = null,
    val claim: String? = null,
    val verdict: String? = null,
    val category: String? = null,
    @SerializedName("evidence_sufficiency") val evidenceSufficiency: String? = null,
    val basis: String? = null,
    val uncertainty: String? = null,
    @SerializedName("source_ids") val sourceIds: List<String>? = null,
)

data class NarrativeAnalysisDto(
    val verdict: String? = null,
    val methods: List<String>? = null,
    val explanation: String? = null,
)

data class EvidenceDto(
    val id: String? = null,
    val title: String? = null,
    val url: String? = null,
    @SerializedName("source_name") val sourceName: String? = null,
    @SerializedName("published_date") val publishedDate: String? = null,
    val author: String? = null,
    val relation: String? = null,
    val snippet: String? = null,
)

data class VerificationDetailsDto(
    val status: String? = null,
    val message: String? = null,
    val topic: String? = null,
    @SerializedName("overall_verdict") val overallVerdict: String? = null,
    val conclusion: String? = null,
    @SerializedName("sharing_advice") val sharingAdvice: String? = null,
    @SerializedName("claim_checks") val claimChecks: List<ClaimCheckDto>? = null,
    @SerializedName("narrative_analysis") val narrativeAnalysis: NarrativeAnalysisDto? = null,
    @SerializedName("evidence_gaps") val evidenceGaps: List<String>? = null,
    @SerializedName("evidence_used") val evidenceUsed: List<EvidenceDto>? = null,
    @SerializedName("evidence_reviewed_count") val evidenceReviewedCount: Int = 0,
    @SerializedName("evidence_selected_count") val evidenceSelectedCount: Int = 0,
    @SerializedName("report_markdown") val reportMarkdown: String? = null,
)

data class StructuredInformationDto(
    val topic: String? = null,
    val claims: List<Map<String, Any?>>? = null,
)

data class AnalysisDto(
    val verification: VerificationDetailsDto? = null,
    val metadata: ContentMetadataDto? = null,
    val strategy: String? = null,
    @SerializedName("structured_data") val structuredData: StructuredInformationDto? = null,
    @SerializedName("transcript_chars") val transcriptChars: Int? = null,
)

data class JobResultDto(
    val card: MobileCardDto,
    val analysis: AnalysisDto? = null,
)

