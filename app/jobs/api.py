from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.jobs.models import CreateJobRequest, CreateJobResponse, JobSource, JobView, utc_now
from app.jobs.runtime import runtime
from app.jobs.uploads import UploadBundleError, cleanup_upload_bundle, stage_upload_bundle


router = APIRouter(prefix="/v1/jobs", tags=["mobile-jobs"])


def _device_id(value: str | None) -> str:
    return (value or "anonymous-demo-device").strip()[:128]


@router.post("", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(request: CreateJobRequest, x_device_id: str | None = Header(default=None)) -> CreateJobResponse:
    job, reused = await runtime.create(request, _device_id(x_device_id))
    return CreateJobResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        event_url=f"/v1/jobs/{job.job_id}/events",
        reused=reused,
    )


@router.post("/upload", response_model=CreateJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_upload_job(
    title: str = Form(default="手动多模态核验", max_length=200),
    text: str = Form(default="", max_length=50_000),
    files: list[UploadFile] = File(default=[]),
    mode: str = Form(default="auto", pattern="^(auto|visual)$"),
    verification_mode: str = Form(default="speed", pattern="^(speed|quality)$"),
    client_request_id: str = Form(min_length=8, max_length=100),
    x_device_id: str | None = Header(default=None),
) -> CreateJobResponse:
    try:
        bundle_id = await stage_upload_bundle(title, text, files)
    except UploadBundleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request = CreateJobRequest(
        source=JobSource(
            type="upload_bundle",
            value=bundle_id,
            platform_hint="user_upload",
        ),
        mode=mode,
        verification_mode=verification_mode,
        client_request_id=client_request_id,
    )
    try:
        job, reused = await runtime.create(request, _device_id(x_device_id))
    except Exception:
        cleanup_upload_bundle(bundle_id)
        raise
    if reused:
        cleanup_upload_bundle(bundle_id)
    return CreateJobResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        event_url=f"/v1/jobs/{job.job_id}/events",
        reused=reused,
    )


@router.get("", response_model=list[JobView])
async def list_jobs(x_device_id: str | None = Header(default=None), limit: int = 50) -> list[JobView]:
    await runtime.initialize()
    return await runtime.store.list(_device_id(x_device_id), min(max(limit, 1), 100))


async def _get_job(job_id: str) -> JobView:
    await runtime.initialize()
    job = await runtime.store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="核验任务不存在")
    return job


@router.get("/{job_id}", response_model=JobView)
async def get_job(job_id: str) -> JobView:
    return await _get_job(job_id)


@router.get("/{job_id}/result")
async def get_result(job_id: str) -> dict:
    job = await _get_job(job_id)
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=409, detail="核验尚未完成")
    return job.result


@router.get("/{job_id}/report", response_class=PlainTextResponse)
async def get_report(job_id: str) -> str:
    job = await _get_job(job_id)
    report = (((job.result or {}).get("analysis") or {}).get("verification") or {}).get("report_markdown")
    if not report:
        raise HTTPException(status_code=404, detail="审计报告不存在")
    return str(report)


@router.get("/{job_id}/events")
async def job_events(job_id: str, last_event_id: str | None = Header(default=None)) -> StreamingResponse:
    await _get_job(job_id)
    try:
        initial_sequence = max(0, int(last_event_id or 0))
    except ValueError:
        initial_sequence = 0

    async def stream():
        sequence = initial_sequence
        while True:
            events = await runtime.events.read(job_id, sequence, timeout=15)
            if not events:
                yield ": keep-alive\n\n"
                continue
            for event in events:
                sequence = max(sequence, event.sequence)
                yield f"id: {event.sequence}\nevent: job-stage\ndata: {event.model_dump_json()}\n\n"
            current = await runtime.store.get(job_id)
            if current and current.status in {"completed", "failed", "cancelled"} and sequence >= current.sequence:
                break

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{job_id}/cancel", response_model=JobView)
async def cancel_job(job_id: str) -> JobView:
    job = await _get_job(job_id)
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    return await runtime.store.update(job_id, cancel_requested=True, display_text="正在取消核验")


@router.delete("/{job_id}/source", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(job_id: str) -> Response:
    await _get_job(job_id)
    await runtime.store.redact_source(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
