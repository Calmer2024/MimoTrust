from __future__ import annotations

import asyncio
import json
import time
from inspect import isawaitable
from pathlib import Path
from typing import Awaitable, Callable, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.cache import ResultCache
from app.config import settings
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeleteResponse,
    StageTiming,
    StoredVideoList,
    StructuredInformation,
    VerifyRequest,
)
from app.pipeline import (
    PipelineError,
    _clean_source_article,
    _structured_reading_result,
    analyze,
)
from app.content import analyze_article_url, analyze_upload_bundle
from app.security import ALLOWED_HOST_SUFFIXES, UnsafeUrlError, resolve_content_input
from app.thumbnails import thumbnail_store
from app.trust.service import (
    hydrate_cached_verification,
    verify_structured_information,
)
from app.jobs.api import router as jobs_router
from app.controlled_content import router as controlled_content_router


app = FastAPI(
    title="MiMo Trust Multimodal Source Verification",
    version="0.6.0",
    docs_url="/api/docs",
)


DIRECT_VIDEO_SUFFIXES = {
    ".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".flv", ".m3u8",
}


def _is_direct_video_url(url: str) -> bool:
    """Identify an authorized public media asset without treating it as HTML."""
    return Path(urlparse(url).path).suffix.lower() in DIRECT_VIDEO_SUFFIXES


cache = ResultCache(settings.cache_ttl_seconds)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(jobs_router)
app.include_router(controlled_content_router)


async def _stabilize_result_thumbnail(result: AnalyzeResponse) -> bool:
    original = result.metadata.thumbnail
    if not original or original.startswith("/api/thumbnails/"):
        return False
    result.metadata.thumbnail = await asyncio.to_thread(
        thumbnail_store.materialize,
        original,
        result.metadata.webpage_url,
    )
    return result.metadata.thumbnail != original


async def _stabilize_payload_thumbnail(payload: dict[str, object]) -> None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return
    original = metadata.get("thumbnail")
    if not isinstance(original, str) or not original or original.startswith(
        "/api/thumbnails/"
    ):
        return
    metadata["thumbnail"] = await asyncio.to_thread(
        thumbnail_store.materialize,
        original,
        str(metadata.get("webpage_url") or ""),
    )


def _visible_verification_milliseconds(result: AnalyzeResponse) -> int:
    timing = (result.verification or {}).get("timings") or {}
    stages = timing.get("stages") or {}
    if isinstance(stages, dict) and stages:
        return round(sum(float(value or 0) for value in stages.values()) * 1000)
    return round(float(timing.get("total_seconds") or 0) * 1000)


def _visible_extraction_milliseconds(result: AnalyzeResponse) -> int:
    return sum(max(0, int(item.milliseconds)) for item in result.timings)


def _finalize_request_timings(
    result: AnalyzeResponse,
    *,
    full_milliseconds: int,
    input_milliseconds: int,
    thumbnail_milliseconds: int,
) -> None:
    visible_core = (
        _visible_extraction_milliseconds(result)
        + _visible_verification_milliseconds(result)
    )
    # Millisecond rounding can make nested timers exceed the outer wall clock
    # by 1–2 ms. Preserve a non-negative exact partition in that edge case.
    full = max(0, int(full_milliseconds), visible_core)
    remaining = full - visible_core
    input_time = min(max(0, int(input_milliseconds)), remaining)
    remaining -= input_time
    thumbnail_time = min(max(0, int(thumbnail_milliseconds)), remaining)
    remaining -= thumbnail_time
    result.orchestration_timings = [
        StageTiming(name="输入解析与安全展开", milliseconds=input_time),
        StageTiming(name="封面获取与转存", milliseconds=thumbnail_time),
        StageTiming(name="其他编排开销", milliseconds=remaining),
    ]
    result.full_pipeline_milliseconds = full


def _ensure_request_timings(result: AnalyzeResponse) -> None:
    if result.orchestration_timings:
        return
    verification_total = round(
        float(((result.verification or {}).get("timings") or {}).get(
            "total_seconds", 0
        )) * 1000
    )
    historical_full = result.full_pipeline_milliseconds or (
        result.extraction_milliseconds + verification_total
    )
    _finalize_request_timings(
        result,
        full_milliseconds=historical_full,
        input_milliseconds=0,
        thumbnail_milliseconds=0,
    )


def _ensure_payload_request_timings(payload: dict[str, object]) -> None:
    try:
        result = AnalyzeResponse.model_validate(payload)
    except Exception:
        return
    _ensure_request_timings(result)
    payload.clear()
    payload.update(result.model_dump(mode="json"))


def _ensure_cleaned_article(payload: dict[str, object]) -> dict[str, object]:
    metadata = payload.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    full_source_text = str(payload.get("full_source_text") or "")
    if not payload.get("structured_input_text") and full_source_text:
        structured_input = full_source_text[: settings.max_transcript_chars]
        payload["structured_input_text"] = structured_input
        payload["structured_input_chars"] = len(structured_input)
        payload["structured_input_truncated"] = (
            len(full_source_text) > settings.max_transcript_chars
        )
    if not payload.get("cleaned_article"):
        payload["cleaned_article"] = _clean_source_article(
            full_source_text,
            str(metadata_dict.get("title") or ""),
        )
    structured_payload = payload.get("structured_data")
    if isinstance(structured_payload, dict):
        structured = StructuredInformation.model_validate(structured_payload)
        summary, _, _ = _structured_reading_result(structured)
        payload["summary"] = summary
    verification = payload.get("verification")
    if isinstance(verification, dict):
        payload["verification"] = hydrate_cached_verification(verification)
    return payload


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(
        static_dir / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mimo_configured": bool(settings.mimo_api_key),
        "supported_platforms": [
            "抖音", "哔哩哔哩", "YouTube", "快手", "微博", "小红书", "视频号"
        ],
        "accepted_inputs": [
            "文章 URL", "平台链接/分享文本", "无有效链接时自动组合文本+图片+音频+视频"
        ],
        "extraction_protocol": "compact-claims-v2",
        "job_mode": settings.job_mode,
        "mobile_job_api": "/v1/jobs",
    }


@app.get("/api/thumbnails/{key}", include_in_schema=False)
async def thumbnail(key: str) -> FileResponse:
    path = thumbnail_store.get_path(key)
    if not path:
        raise HTTPException(status_code=404, detail="封面不存在或已过期")
    return FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


async def _execute_analysis(
    request: AnalyzeRequest,
    progress: Callable[[str], None | Awaitable[None]] | None = None,
    stream: Callable[[str, str], None | Awaitable[None]] | None = None,
    product: Callable[[dict[str, object]], None | Awaitable[None]] | None = None,
) -> AnalyzeResponse:
    async def emit(message: str) -> None:
        if progress is None:
            return
        result = progress(message)
        if isawaitable(result):
            await result

    request_started = time.perf_counter()
    await emit("正在解析并安全展开输入")
    input_started = time.perf_counter()
    try:
        url = await asyncio.to_thread(
            resolve_content_input,
            request.url,
            platform_only=request.input_kind == "platform",
        )
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    input_milliseconds = round((time.perf_counter() - input_started) * 1000)

    cache_key = cache.key(f"{request.input_kind}:{url}", request.mode)
    if not request.refresh:
        cached = cache.get(cache_key)
        if cached:
            await emit("命中内容缓存，正在恢复完整结果")
            cached["cached"] = True
            _ensure_cleaned_article(cached)
            cached_result = AnalyzeResponse.model_validate(cached)
            _ensure_request_timings(cached_result)
            thumbnail_changed = await _stabilize_result_thumbnail(cached_result)
            verification_added = False
            cached_verification_mode = str(
                (cached_result.verification or {}).get("verification_mode") or ""
            )
            if request.verify and (
                not cached_result.verification
                or cached_verification_mode != request.verification_mode
            ):
                try:
                    cached_result.verification = await verify_structured_information(
                        cached_result.structured_data,
                        request.verification_mode,
                        source_url=cached_result.metadata.webpage_url,
                        source_context=cached_result.full_source_text,
                        progress=progress,
                        stream=stream,
                        product=product,
                    )
                    verification_added = True
                except Exception as exc:
                    cached_result.verification = {
                        "status": "failed",
                        "message": str(exc),
                    }
            if not cached_result.extraction_milliseconds:
                cached_result.extraction_milliseconds = sum(
                    item.milliseconds for item in cached_result.timings
                )
            verification_seconds = float(
                ((cached_result.verification or {}).get("timings") or {}).get(
                    "total_seconds", 0
                )
            )
            if not cached_result.full_pipeline_milliseconds:
                cached_result.full_pipeline_milliseconds = (
                    cached_result.extraction_milliseconds
                    + round(verification_seconds * 1000)
                )
            if verification_added:
                cached_result.full_pipeline_milliseconds = (
                    _visible_extraction_milliseconds(cached_result)
                    + _visible_verification_milliseconds(cached_result)
                    + sum(
                        item.milliseconds
                        for item in cached_result.orchestration_timings
                    )
                )
            if verification_added or thumbnail_changed:
                cache.set(cache_key, cached_result.model_dump(mode="json"))
            return cached_result

    try:
        await emit("正在提取内容并生成核心主张")
        hostname = (urlparse(url).hostname or "").lower()
        is_platform = any(
            hostname == suffix or hostname.endswith(f".{suffix}")
            for suffix in ALLOWED_HOST_SUFFIXES
        )
        is_direct_video = _is_direct_video_url(url)
        if request.input_kind == "article" or (
            not is_platform and not is_direct_video
        ):
            result = await analyze_article_url(url)
        else:
            try:
                result = await analyze(url, request.mode)
            except PipelineError:
                if (
                    request.input_kind == "platform"
                    or is_platform
                    or is_direct_video
                ):
                    raise
                result = await analyze_article_url(url)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    thumbnail_started = time.perf_counter()
    await _stabilize_result_thumbnail(result)
    thumbnail_milliseconds = round(
        (time.perf_counter() - thumbnail_started) * 1000
    )

    if request.verify:
        try:
            result.verification = await verify_structured_information(
                result.structured_data,
                request.verification_mode,
                source_url=result.metadata.webpage_url,
                source_context=result.full_source_text,
                progress=progress,
                stream=stream,
                product=product,
            )
        except Exception as exc:
            result.verification = {
                "status": "failed",
                "message": str(exc),
            }
    _finalize_request_timings(
        result,
        full_milliseconds=round(
            (time.perf_counter() - request_started) * 1000
        ),
        input_milliseconds=input_milliseconds,
        thumbnail_milliseconds=thumbnail_milliseconds,
    )
    cache.set(cache_key, result.model_dump(mode="json"))
    return result


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_content(request: AnalyzeRequest) -> AnalyzeResponse:
    return await _execute_analysis(request)


def _sse(event: str, payload: dict[str, object]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


@app.post("/api/analyze/stream")
async def analyze_content_stream(request: AnalyzeRequest) -> StreamingResponse:
    async def events():
        queue: asyncio.Queue[tuple[str, dict[str, object]]] = asyncio.Queue()

        async def emit(message: str) -> None:
            await queue.put(("progress", {"type": "progress", "message": message}))

        async def emit_stream(kind: str, text: str) -> None:
            await queue.put((f"{kind}_delta", {"type": f"{kind}_delta", "text": text}))

        async def emit_product(payload: dict[str, object]) -> None:
            await queue.put(("artifact", {"type": "artifact", "data": payload}))

        async def worker() -> None:
            try:
                result = await _execute_analysis(
                    request, emit, emit_stream, emit_product
                )
                await queue.put(("result", {
                    "type": "result",
                    "data": result.model_dump(mode="json", by_alias=True),
                }))
            except HTTPException as exc:
                await queue.put(("error", {
                    "type": "error",
                    "message": str(exc.detail),
                }))
            except Exception as exc:
                await queue.put(("error", {
                    "type": "error",
                    "message": str(exc),
                }))

        task = asyncio.create_task(worker())
        try:
            while True:
                event, payload = await queue.get()
                yield _sse(event, payload)
                if event in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _execute_uploaded_analysis(
    title: str,
    text: str,
    files: list[UploadFile],
    verify: bool,
    verification_mode: Literal["speed", "quality"],
    progress: Callable[[str], None | Awaitable[None]] | None = None,
    stream: Callable[[str, str], None | Awaitable[None]] | None = None,
    product: Callable[[dict[str, object]], None | Awaitable[None]] | None = None,
) -> AnalyzeResponse:
    async def emit(message: str) -> None:
        if progress is None:
            return
        result = progress(message)
        if isawaitable(result):
            await result

    request_started = time.perf_counter()
    await emit("正在理解上传材料并提取核心主张")
    try:
        result = await analyze_upload_bundle(title.strip(), text, files)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"多模态材料解析失败：{exc}"
        ) from exc
    thumbnail_started = time.perf_counter()
    await _stabilize_result_thumbnail(result)
    thumbnail_milliseconds = round(
        (time.perf_counter() - thumbnail_started) * 1000
    )
    if verify:
        try:
            result.verification = await verify_structured_information(
                result.structured_data,
                verification_mode,
                source_url=result.metadata.webpage_url,
                source_context=result.full_source_text,
                progress=progress,
                stream=stream,
                product=product,
            )
        except Exception as exc:
            result.verification = {"status": "failed", "message": str(exc)}
    _finalize_request_timings(
        result,
        full_milliseconds=round(
            (time.perf_counter() - request_started) * 1000
        ),
        input_milliseconds=0,
        thumbnail_milliseconds=thumbnail_milliseconds,
    )
    return result


@app.post("/api/analyze/upload", response_model=AnalyzeResponse)
async def analyze_uploaded_content(
    title: str = Form(default="多模态组合核验", max_length=200),
    text: str = Form(default="", max_length=50_000),
    files: list[UploadFile] = File(default=[]),
    verify: bool = Form(default=True),
    verification_mode: Literal["speed", "quality"] = Form(default="speed"),
) -> AnalyzeResponse:
    return await _execute_uploaded_analysis(
        title, text, files, verify, verification_mode
    )


@app.post("/api/analyze/upload/stream")
async def analyze_uploaded_content_stream(
    title: str = Form(default="多模态组合核验", max_length=200),
    text: str = Form(default="", max_length=50_000),
    files: list[UploadFile] = File(default=[]),
    verify: bool = Form(default=True),
    verification_mode: Literal["speed", "quality"] = Form(default="speed"),
) -> StreamingResponse:
    async def events():
        queue: asyncio.Queue[tuple[str, dict[str, object]]] = asyncio.Queue()

        async def emit(message: str) -> None:
            await queue.put(("progress", {"type": "progress", "message": message}))

        async def emit_stream(kind: str, text: str) -> None:
            await queue.put((f"{kind}_delta", {"type": f"{kind}_delta", "text": text}))

        async def emit_product(payload: dict[str, object]) -> None:
            await queue.put(("artifact", {"type": "artifact", "data": payload}))

        async def worker() -> None:
            try:
                result = await _execute_uploaded_analysis(
                    title,
                    text,
                    files,
                    verify,
                    verification_mode,
                    emit,
                    emit_stream,
                    emit_product,
                )
                await queue.put(("result", {
                    "type": "result",
                    "data": result.model_dump(mode="json", by_alias=True),
                }))
            except HTTPException as exc:
                await queue.put(("error", {
                    "type": "error",
                    "message": str(exc.detail),
                }))
            except Exception as exc:
                await queue.put(("error", {
                    "type": "error",
                    "message": str(exc),
                }))

        task = asyncio.create_task(worker())
        try:
            while True:
                event, payload = await queue.get()
                yield _sse(event, payload)
                if event in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/verify")
async def verify_claims(request: VerifyRequest) -> dict[str, object]:
    try:
        source_context = None
        source_url = None
        cached: dict[str, object] | None = None
        if request.cache_key:
            cached = cache.get(request.cache_key)
            if not cached:
                raise HTTPException(status_code=404, detail="缓存记录不存在或已过期")
            source_context = str(cached.get("full_source_text") or "")
            metadata = cached.get("metadata")
            if isinstance(metadata, dict):
                source_url = str(metadata.get("webpage_url") or "") or None
        result = await verify_structured_information(
            request.structured_data,
            request.verification_mode,
            source_url=source_url,
            source_context=source_context,
        )
        if request.cache_key:
            assert cached is not None
            cached_structured = StructuredInformation.model_validate(
                cached.get("structured_data", {})
            )
            if cached_structured != request.structured_data:
                raise HTTPException(status_code=409, detail="核验案例与缓存记录不匹配")
            cached["verification"] = result
            try:
                cached_result = AnalyzeResponse.model_validate(cached)
            except Exception:
                # Compatibility with early/minimal cache fixtures that only
                # persisted structured_data.
                cache.set(request.cache_key, cached)
            else:
                _ensure_request_timings(cached_result)
                cached_result.full_pipeline_milliseconds = (
                    _visible_extraction_milliseconds(cached_result)
                    + _visible_verification_milliseconds(cached_result)
                    + sum(
                        item.milliseconds
                        for item in cached_result.orchestration_timings
                    )
                )
                cache.set(
                    request.cache_key,
                    cached_result.model_dump(mode="json"),
                )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/videos", response_model=StoredVideoList)
async def list_videos(limit: int = 100) -> StoredVideoList:
    safe_limit = min(max(limit, 1), 500)
    items = cache.list(safe_limit)
    for item in items:
        result = item.get("result")
        if isinstance(result, dict):
            _ensure_cleaned_article(result)
            _ensure_payload_request_timings(result)
    await asyncio.gather(*(
        _stabilize_payload_thumbnail(item["result"])
        for item in items
        if isinstance(item.get("result"), dict)
    ))
    return StoredVideoList.model_validate({"items": items, "total": len(items)})


@app.delete("/api/videos/{cache_key}", response_model=DeleteResponse)
async def delete_video(cache_key: str) -> DeleteResponse:
    deleted = cache.delete(cache_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="缓存记录不存在")
    return DeleteResponse(deleted=deleted)


@app.delete("/api/videos", response_model=DeleteResponse)
async def clear_videos() -> DeleteResponse:
    return DeleteResponse(deleted=cache.clear())
