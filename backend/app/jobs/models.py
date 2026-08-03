from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
JobStage = Literal[
    "queued",
    "content_resolving",
    "media_extracting",
    "claim_structuring",
    "evidence_retrieval",
    "evidence_triage",
    "report_generating",
    "completed",
    "failed",
    "cancelled",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobSource(BaseModel):
    type: Literal[
        "shared_url",
        "agent_context",
        "platform_api",
        "upload_bundle",
        "controlled_manifest",
    ] = "shared_url"
    value: str = Field(min_length=1, max_length=100_000)
    platform_hint: str | None = Field(default=None, max_length=50)


class CreateJobRequest(BaseModel):
    source: JobSource
    mode: Literal["auto", "visual"] = "auto"
    verification_mode: Literal["speed", "quality"] = "speed"
    client_request_id: str = Field(min_length=8, max_length=100)


class JobEvent(BaseModel):
    event_id: str
    job_id: str
    sequence: int
    stage: JobStage
    state: Literal["pending", "running", "completed", "failed", "cancelled"]
    display_text: str
    elapsed_ms: int = 0
    progress_hint: int = Field(ge=0, le=100)
    content_metadata: dict[str, Any] | None = None
    event_kind: Literal[
        "stage", "thinking_delta", "report_delta", "stream_reset", "artifact"
    ] = "stage"
    payload: dict[str, Any] | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class JobView(BaseModel):
    job_id: str
    device_id: str
    client_request_id: str
    source: JobSource
    mode: Literal["auto", "visual"] = "auto"
    verification_mode: Literal["speed", "quality"] = "speed"
    status: JobStatus = "queued"
    stage: JobStage = "queued"
    display_text: str = "小真已接收，等待开始核验"
    progress_hint: int = 0
    sequence: int = 0
    elapsed_ms: int = 0
    cancel_requested: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    event_url: str
    reused: bool = False


class EvidenceSummary(BaseModel):
    title: str
    url: str | None = None
    source_name: str | None = None


class MobileResultCard(BaseModel):
    job_id: str
    verdict: str
    headline: str
    conclusion: str
    evidence_count: int = 0
    elapsed_ms: int = 0
    completed_at: datetime
    key_evidence: list[EvidenceSummary] = Field(default_factory=list)
    uncertainty_note: str | None = None
    report_url: str | None = None
    ai_disclaimer: str = "AI 辅助核验，仅供信息参考"

