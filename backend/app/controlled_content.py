from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.jobs.models import CreateJobRequest, JobSource, JobView
from app.jobs.runtime import runtime
from app.security import UnsafeUrlError, validate_public_url


router = APIRouter(prefix="/v1/controlled-content", tags=["controlled-content"])

MAX_EXCHANGE_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_JOB_BYTES = 100_000
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class GrantExchangeRequest(BaseModel):
    exchange_url: str = Field(min_length=8, max_length=2_048)
    grant_code: str = Field(min_length=1, max_length=4_096)
    audience: str = Field(min_length=1, max_length=256)
    content_id: str = Field(min_length=1, max_length=256)
    content_version: str = Field(min_length=1, max_length=128)


class ContextProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: Literal["mimotrust_sandbox"]
    application_id: Literal["com.mimotrust.controlledcontent"]


class ContextContentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: Literal[
        "video", "audio", "article", "rich_article", "image_gallery"
    ]
    content_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    content_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_url: str = Field(min_length=9, max_length=2_048)

    @field_validator("canonical_url")
    @classmethod
    def canonical_url_must_use_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("canonical_url must use HTTPS")
        return value


class ContextGrantAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["grant_exchange"]
    exchange_url: AnyHttpUrl
    grant_code: str = Field(min_length=1, max_length=512)
    audience: Literal["mimotrust_guardian_backend"]
    expires_at: datetime
    scopes: list[Literal["manifest:read", "asset:read"]] = Field(min_length=1)

    @field_validator("expires_at")
    @classmethod
    def grant_must_be_fresh(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value <= datetime.now(timezone.utc):
            raise ValueError("grant has expired")
        return value

    @field_validator("scopes")
    @classmethod
    def scopes_must_cover_analysis(cls, value: list[str]) -> list[str]:
        if not {"manifest:read", "asset:read"}.issubset(value):
            raise ValueError("grant scopes do not cover analysis")
        if len(value) != len(set(value)):
            raise ValueError("grant scopes must be unique")
        return value


class MediaViewState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    is_playing: bool

    @model_validator(mode="after")
    def position_must_fit_duration(self) -> "MediaViewState":
        if self.position_ms > self.duration_ms:
            raise ValueError("position_ms exceeds duration_ms")
        return self


class ReadingViewState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scroll_ratio: float = Field(ge=0, le=1)
    block_index: int = Field(ge=0)


class GalleryViewState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_asset_index: int = Field(ge=0)
    asset_count: int = Field(gt=0)

    @model_validator(mode="after")
    def index_must_fit_count(self) -> "GalleryViewState":
        if self.active_asset_index >= self.asset_count:
            raise ValueError("active_asset_index exceeds asset_count")
        return self


class GuardianContentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.2"]
    event_id: UUID
    trigger: Literal["guardian_request"]
    source_app: Literal["mimotrust_controlled_content"]
    provider: ContextProvider
    content_ref: ContextContentRef
    content_access: ContextGrantAccess
    view_state: MediaViewState | ReadingViewState | GalleryViewState
    observed_at: datetime

    @model_validator(mode="after")
    def view_state_must_match_content_type(self) -> "GuardianContentContext":
        content_type = self.content_ref.content_type
        if content_type in {"video", "audio"} and not isinstance(
            self.view_state, MediaViewState
        ):
            raise ValueError("media content requires media view_state")
        if content_type in {"article", "rich_article"} and not isinstance(
            self.view_state, ReadingViewState
        ):
            raise ValueError("article content requires reading view_state")
        if content_type == "image_gallery" and not isinstance(
            self.view_state, GalleryViewState
        ):
            raise ValueError("gallery content requires gallery view_state")
        return self


class ContentContextSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    guardian_app_version: str = Field(min_length=1, max_length=64)
    context: GuardianContentContext

    @model_validator(mode="after")
    def request_id_must_match_event_id(self) -> "ContentContextSubmission":
        if self.request_id != self.context.event_id:
            raise ValueError("request_id does not match context.event_id")
        return self


async def _exchange_with_gateway(request: GrantExchangeRequest) -> dict[str, object]:
    try:
        validate_public_url(request.exchange_url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    upstream_payload = request.model_dump(exclude={"exchange_url"})
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(20),
        ) as client:
            response = await client.post(request.exchange_url, json=upstream_payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="内容授权交换超时") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="内容授权交换网络失败") from exc

    if response.is_redirect:
        raise HTTPException(status_code=502, detail="内容授权交换不接受重定向")
    if not response.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"内容授权交换失败：上游状态 {response.status_code}",
        )
    if len(response.content) > MAX_EXCHANGE_RESPONSE_BYTES:
        raise HTTPException(status_code=502, detail="内容授权交换响应过大")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="内容授权交换返回了无效 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise HTTPException(status_code=502, detail="内容授权交换响应缺少 manifest")
    return payload


def _validate_manifest(
    payload: dict[str, object], context: GuardianContentContext
) -> dict[str, object]:
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=502, detail="内容授权交换响应缺少 manifest")
    if manifest.get("manifest_version") != "1.0":
        raise HTTPException(status_code=502, detail="不支持的 Content Manifest 版本")
    provider = manifest.get("provider")
    if not isinstance(provider, dict) or provider.get("provider_id") != "mimotrust_sandbox":
        raise HTTPException(status_code=502, detail="Content Manifest provider 不匹配")
    content = manifest.get("content")
    if not isinstance(content, dict):
        raise HTTPException(status_code=502, detail="Content Manifest 缺少 content")
    expected = context.content_ref
    comparisons = {
        "content_type": expected.content_type,
        "content_id": expected.content_id,
        "content_version": expected.content_version,
        "content_hash": expected.content_hash,
        "canonical_url": expected.canonical_url,
    }
    for field, expected_value in comparisons.items():
        if content.get(field) != expected_value:
            raise HTTPException(status_code=502, detail=f"Content Manifest {field} 不匹配")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise HTTPException(status_code=502, detail="Content Manifest 缺少 assets")
    analysis_assets: list[dict[str, object]] = []
    asset_ids: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise HTTPException(status_code=502, detail="Content Manifest asset 无效")
        asset_id = asset.get("asset_id")
        if (
            not isinstance(asset_id, str)
            or not asset_id
            or asset_id in asset_ids
            or asset.get("role") not in {"original", "playback", "analysis", "cover", "subtitle"}
            or not isinstance(asset.get("source_url"), str)
            or not isinstance(asset.get("mime_type"), str)
            or not isinstance(asset.get("size_bytes"), int)
            or asset["size_bytes"] <= 0
            or not isinstance(asset.get("sha256"), str)
            or not SHA256_PATTERN.fullmatch(asset["sha256"])
        ):
            raise HTTPException(status_code=502, detail="Content Manifest asset 字段无效")
        asset_ids.add(asset_id)
        if asset.get("role") == "analysis":
            analysis_assets.append(asset)

    blocks = content.get("blocks")
    has_text_blocks = isinstance(blocks, list) and any(
        isinstance(block, dict)
        and block.get("block_type") == "text"
        and isinstance(block.get("text"), str)
        and bool(block["text"].strip())
        for block in blocks
    )
    analysis_mimes = [str(asset["mime_type"]).lower() for asset in analysis_assets]
    required_prefixes = {
        "video": ("video/",),
        "audio": ("audio/",),
        "image_gallery": ("image/",),
    }
    required = required_prefixes.get(expected.content_type)
    if required and not any(mime.startswith(required) for mime in analysis_mimes):
        raise HTTPException(status_code=502, detail="Content Manifest 缺少对应类型的分析素材")
    if expected.content_type == "article" and not (
        has_text_blocks or any(mime.startswith("text/") for mime in analysis_mimes)
    ):
        raise HTTPException(status_code=502, detail="Content Manifest 缺少文章正文")
    if expected.content_type == "rich_article" and not (
        has_text_blocks
        or any(mime.startswith(("text/", "image/")) for mime in analysis_mimes)
    ):
        raise HTTPException(status_code=502, detail="Content Manifest 缺少图文分析内容")
    binary_analysis_count = sum(
        mime.startswith(("image/", "audio/", "video/")) for mime in analysis_mimes
    )
    if binary_analysis_count > 12:
        raise HTTPException(status_code=502, detail="Content Manifest 分析素材超过 12 个")
    return manifest


def _device_id(value: str | None) -> str:
    normalized = (value or "").strip()[:128]
    return normalized or "anonymous-demo-device"


def _submission_response(
    request_id: UUID,
    job: JobView,
    *,
    reused: bool,
) -> dict[str, object]:
    cache_status = "miss"
    if reused:
        cache_status = "exact_hit" if job.status == "completed" else "in_progress"
    return {
        "request_id": str(request_id),
        "job_id": job.job_id,
        "accepted": True,
        "cache_status": cache_status,
        "task_status": job.status,
        "status": job.status,
        "created_at": job.created_at,
        "event_url": f"/v1/jobs/{job.job_id}/events",
        "reused": reused,
    }


@router.post("/exchange")
async def exchange_controlled_content_grant(
    request: GrantExchangeRequest,
) -> dict[str, object]:
    """Exchange a Sandbox grant through the local service used by the device."""
    return await _exchange_with_gateway(request)


content_context_router = APIRouter(tags=["controlled-content"])


@content_context_router.post("/v1/content-contexts", status_code=status.HTTP_202_ACCEPTED)
async def submit_content_context(
    submission: ContentContextSubmission,
    x_device_id: str | None = Header(default=None),
) -> dict[str, object]:
    context = submission.context
    access = context.content_access
    device_id = _device_id(x_device_id)
    existing = await runtime.get_by_identity(device_id, str(submission.request_id))
    if existing is not None:
        return _submission_response(submission.request_id, existing, reused=True)
    exchanged = await _exchange_with_gateway(
        GrantExchangeRequest(
            exchange_url=str(access.exchange_url),
            grant_code=access.grant_code,
            audience=access.audience,
            content_id=context.content_ref.content_id,
            content_version=context.content_ref.content_version,
        )
    )
    manifest = _validate_manifest(exchanged, context)
    manifest_json = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    if len(manifest_json.encode("utf-8")) > MAX_MANIFEST_JOB_BYTES:
        raise HTTPException(status_code=502, detail="Content Manifest 超过任务输入上限")
    request = CreateJobRequest(
        source=JobSource(
            type="controlled_manifest",
            value=manifest_json,
            platform_hint="mimotrust_sandbox",
        ),
        client_request_id=str(submission.request_id),
    )
    job, reused = await runtime.create(request, device_id)
    return _submission_response(submission.request_id, job, reused=reused)
