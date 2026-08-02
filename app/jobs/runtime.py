from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.jobs.events import EventBus, MemoryEventBus, RedisEventBus
from app.jobs.models import CreateJobRequest, JobEvent, JobView, utc_now
from app.jobs.store import JobStore, MemoryJobStore, SqlJobStore


class JobRuntime:
    def __init__(self, mode: str | None = None) -> None:
        self.mode = (mode or settings.job_mode).lower()
        self.store: JobStore = (
            SqlJobStore(settings.database_url)
            if self.mode == "distributed"
            else MemoryJobStore()
        )
        self.events: EventBus = (
            RedisEventBus(settings.redis_url)
            if self.mode == "distributed"
            else MemoryEventBus()
        )
        self._initialized = False
        self._initialize_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if not self._initialized:
                await self.store.initialize()
                self._initialized = True

    async def create(self, request: CreateJobRequest, device_id: str) -> tuple[JobView, bool]:
        await self.initialize()
        job = JobView(
            job_id=str(uuid4()),
            device_id=device_id,
            client_request_id=request.client_request_id,
            source=request.source,
            mode=request.mode,
            verification_mode=request.verification_mode,
        )
        job, reused = await self.store.create(job)
        if reused:
            return job, True
        await self.emit(job.job_id, "queued", "pending", "小真已接收，等待开始核验", 0)
        if self.mode == "distributed":
            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("run_job", job.job_id, _queue_name=settings.job_queue_name)
            await pool.close()
        else:
            from app.jobs.worker import process_job

            task = asyncio.create_task(process_job(self, job.job_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return job, False

    async def emit(
        self,
        job_id: str,
        stage: str,
        state: str,
        display_text: str,
        progress_hint: int,
        **changes: Any,
    ) -> JobView:
        current = await self.store.get(job_id)
        if not current:
            raise KeyError(job_id)
        sequence = current.sequence + 1
        content_metadata = changes.pop("content_metadata", None)
        elapsed_ms = changes.pop("elapsed_ms", current.elapsed_ms)
        status = changes.pop("status", current.status)
        event_kind = changes.pop("event_kind", "stage")
        payload = changes.pop("payload", None)
        updated = await self.store.update(
            job_id,
            stage=stage,
            status=status,
            display_text=display_text,
            progress_hint=progress_hint,
            sequence=sequence,
            elapsed_ms=elapsed_ms,
            **changes,
        )
        await self.events.publish(JobEvent(
            event_id=str(uuid4()),
            job_id=job_id,
            sequence=sequence,
            stage=stage,
            state=state,
            display_text=display_text,
            elapsed_ms=elapsed_ms,
            progress_hint=progress_hint,
            content_metadata=content_metadata,
            event_kind=event_kind,
            payload=payload,
        ))
        return updated


runtime = JobRuntime()

