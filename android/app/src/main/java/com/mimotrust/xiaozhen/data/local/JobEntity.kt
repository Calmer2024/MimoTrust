package com.mimotrust.xiaozhen.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "verification_jobs")
data class JobEntity(
    @PrimaryKey val jobId: String,
    val sourceText: String,
    val status: String,
    val stage: String,
    val displayText: String,
    val progress: Int,
    val sequence: Int,
    val elapsedMs: Long,
    val createdAt: String,
    val verdict: String? = null,
    val headline: String? = null,
    val conclusion: String? = null,
    val evidenceCount: Int = 0,
    val claimDetails: String? = null,
    val narrativeAnalysis: String? = null,
    val evidenceGaps: String? = null,
    val keyEvidence: String? = null,
    val sharingAdvice: String? = null,
    val uncertaintyNote: String? = null,
    val reportUrl: String? = null,
    val aiDisclaimer: String? = null,
    val extractedMetadata: String? = null,
    val thinkingText: String? = null,
    val reportDraft: String? = null,
    val reportJson: String? = null,
    val processArtifacts: String? = null,
)

